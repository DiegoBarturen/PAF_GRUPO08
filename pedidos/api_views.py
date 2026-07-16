from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError, PermissionDenied
from rest_framework.mixins import DestroyModelMixin
from pedidos.models import Pedido, ItemPedido
from pedidos.serializers import PedidoSerializer
from catalogo.models import Producto
from pedidos.services import PedidoService
from pedidos.exceptions import ProductoSinStock, TransicionInvalida


class PedidoListCreateAPIView(ListCreateAPIView):
    """
    Endpoint protegido para Clientes:
    - GET: Listar el historial de pedidos optimizado del cliente autenticado.
    - POST: Procesar la creación atómica de un pedido descontando stock.
    """
    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        """Mitiga el problema N+1 mediante select_related y prefetch_related."""
        return Pedido.objects.filter(
            cliente=self.request.user
        ).select_related('negocio', 'cliente').prefetch_related('items__producto')

    def perform_create(self, serializer):
        serializer.save(cliente=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        items_data = request.data.get('items_input', [])
        
        if not items_data:
            return Response(
                {"error": "Debe incluir al menos un ítem en 'items_input' para procesar el pedido."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Reconstruir el formato que espera el service: carrito como dict {str_id: {"producto_id": id, "cantidad": cant}}
            carrito_dict = {}
            for item in items_data:
                pid = item.get('producto')
                carrito_dict[str(pid)] = {
                    "producto_id": pid,
                    "cantidad": item.get('cantidad', 0)
                }
            
            # Construir form_data desde request.data para compatibilidad
            form_data = {
                "telefono": request.data.get("telefono"),
                "metodo_pago": request.data.get("metodo_pago", "efectivo"),
                "direccion_entrega": request.data.get("direccion_entrega"),
                "referencia": request.data.get("referencia", ""),
                "latitud": request.data.get("latitud"),
                "longitud": request.data.get("longitud")
            }

            pedido = PedidoService.procesar_pedido(
                cliente=self.request.user,
                carrito=carrito_dict,
                form_data=form_data,
                cupon_aplicado=request.data.get("cupon")
            )

            response_serializer = self.get_serializer(pedido)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)

        except Producto.DoesNotExist:
            return Response({"error": "Uno de los productos especificados no existe."}, status=status.HTTP_404_NOT_FOUND)
        except ProductoSinStock as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        

class PedidoDetailAPIView(DestroyModelMixin, RetrieveAPIView):
    """
    Endpoint de Solo Lectura (GET) para hacer seguimiento a un pedido específico.
    Filtra dinámicamente según el rol del usuario autenticado.
    """
    serializer_class = PedidoSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.rol == 'negocio':
            return Pedido.objects.filter(negocio=user).prefetch_related('items__producto')
        elif user.rol == 'repartidor':
            return Pedido.objects.filter(repartidor=user).prefetch_related('items__producto')
        return Pedido.objects.filter(cliente=user).prefetch_related('items__producto')

    def delete(self, request, *args, **kwargs):
        """
        Mapea el método HTTP DELETE al DestroyModelMixin, pero aplicando
        lógica de negocio: cancela el pedido y devuelve el stock.
        """
        pedido = self.get_object()
        
        # Validación: Solo se puede cancelar si el pedido sigue "Pendiente"
        if pedido.estado != 'pendiente':
            return Response(
                {"error": "No se puede cancelar un pedido que ya está en preparación o en camino."},
                status=status.HTTP_400_BAD_REQUEST
            )
            
        try:
            with transaction.atomic():
                # 1. Cambiar el estado a cancelado
                pedido.estado = 'cancelado'
                pedido.save()
                
                # 2. Devolver el stock a los productos asociados
                for item in pedido.items.all():
                    producto = item.producto
                    # Bloqueo para evitar problemas de concurrencia
                    producto_db = Producto.objects.select_for_update().get(id=producto.id)
                    producto_db.stock += item.cantidad
                    producto_db.save()
                    
            return Response(
                {"mensaje": f"Pedido #{pedido.id} cancelado con éxito. Stock devuelto al inventario."},
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"error": "Error interno al procesar la cancelación en PostgreSQL."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class CambiarEstadoPedidoAPIView(APIView):
    """
    Endpoint dedicado para que el Negocio o Repartidor cambien el estado de un pedido.
    POST /api/v1/pedidos/<id>/cambiar-estado/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            pedido = Pedido.objects.get(pk=pk)
        except Pedido.DoesNotExist:
            return Response({"error": "El pedido especificado no existe."}, status=status.HTTP_404_NOT_FOUND)

        user = request.user

        # 1. Validación de seguridad: Un cliente no puede cambiarse el estado a sí mismo
        if user.rol == 'cliente':
            raise PermissionDenied("Los clientes no tienen autorización para cambiar el estado de los pedidos.")

        # 2. Extraer el nuevo estado desde el JSON
        nuevo_estado = request.data.get('estado')
        if not nuevo_estado:
            raise ValidationError({"estado": "Este campo es requerido."})

        # 3. Guardar y retornar respuesta usando el Service
        try:
            pedido_actualizado, asignacion = PedidoService.cambiar_estado(pedido, nuevo_estado)
            serializer = PedidoSerializer(pedido_actualizado)
            return Response({
                "mensaje": f"Estado actualizado con éxito a: {pedido_actualizado.get_estado_display()}",
                "pedido": serializer.data
            }, status=status.HTTP_200_OK)
        except TransicionInvalida as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)