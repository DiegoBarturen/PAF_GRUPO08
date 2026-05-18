# pedidos/views.py
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, View
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.contrib import messages
from django.db import transaction
from django.core.exceptions import ValidationError

from pedidos.models import Pedido, ItemPedido
from pedidos.forms import CrearPedidoForm, ActualizarEstadoPedidoForm
from config.choices import EstadoPedido
from catalogo.models import Producto


class PropietarioNegocioMixin(UserPassesTestMixin):
    """
    Garantiza que el usuario logueado pertenezca al rol del negocio.
    Cumple con la sección 4.4 de Autenticación y Control de Accesos de la guía.
    """
    def test_func(self):
        # El usuario debe estar autenticado y tener el flag/rol de negocio activo
        return self.request.user.is_authenticated and getattr(self.request.user, 'es_negocio', False)


class HistorialPedidosClienteListView(LoginRequiredMixin, ListView):
    """
    Lista los pedidos del cliente autenticado.
    Cumple el Entregable 4 (Punto 2): Paginación de 15 por página.
    Cumple la Sesión 3: Optimización con select_related para mitigar el antipatrón N+1.
    """
    model = Pedido
    template_name = 'pedidos/historial_cliente.html'
    context_object_name = 'pedidos'
    paginate_by = 15 

    def get_queryset(self):
        return Pedido.objects.filter(
            cliente=self.request.user
        ).select_related('negocio').order_by('-fecha_creacion')


class PanelNegocioPedidoListView(LoginRequiredMixin, PropietarioNegocioMixin, ListView):
    """
    Panel de control donde el restaurante gestiona sus órdenes entrantes.
    Paginado a 15 y optimizado para base de datos.
    """
    model = Pedido
    template_name = 'pedidos/panel_negocio.html'
    context_object_name = 'pedidos'
    paginate_by = 15

    def get_queryset(self):
        return Pedido.objects.filter(
            negocio__propietario=self.request.user
        ).select_related('cliente').prefetch_related('items_pedido__producto').order_by('-fecha_creacion')


class ProcesarCarritoView(LoginRequiredMixin, View):
    """
    Vista transaccional (ACID) que procesa los productos del carrito,
    descuenta el inventario en PostgreSQL y crea la orden formal.
    """
    def post(self, request, *args, **kwargs):
        form = CrearPedidoForm(request.POST)
        
        if form.is_valid():
            carrito = request.session.get('carrito', {})

            if not carrito:
                messages.error(request, "No puedes procesar un pedido con el carrito vacío.")
                return redirect('catalogo:ver_catalogo')

            try:
                # Bloque de transacción atómica nativa en PostgreSQL (Garantía ACID)
                with transaction.atomic():
                    # 1. Crear la cabecera del pedido (sin guardar en BD aún)
                    pedido = form.save(commit=False)
                    pedido.cliente = request.user
                    pedido.save()  
                    
                    # 2. Procesar cada producto del carrito
                    for producto_id, datos_item in carrito.items():
                        producto = Producto.objects.select_for_update().get(id=producto_id)
                        cantidad = int(datos_item['cantidad'])

                        if producto.stock < cantidad:
                            raise ValidationError(f"Stock insuficiente para el producto: {producto.nombre}")

                        # Descontar stock de forma segura
                        producto.stock -= cantidad
                        producto.save()

                        # NOTA: El método save() de ItemPedido congelará el precio y actualizará los totales del pedido automáticamente.
                        ItemPedido.objects.create(
                            pedido=pedido,
                            producto=producto,
                            cantidad=cantidad,
                            precio_unitario=producto.precio
                        )

                messages.success(request, f"¡Tu pedido #{pedido.id} ha sido recibido con éxito!")
                request.session['carrito'] = {}  # Limpiar el carrito de la sesión
                return redirect('pedidos:historial_cliente')

            except ValidationError as e:
                messages.error(request, f"Error al procesar el pedido: {', '.join(e.messages) if hasattr(e, 'messages') else str(e)}")
                return redirect('pedidos:ver_carrito')
            
            except Exception as e:
                messages.error(request, f"Ocurrió un error inesperado en el servidor: {str(e)}")
                return redirect('pedidos:ver_carrito')

        messages.error(request, "Los datos proporcionados en el formulario son inválidos.")
        return redirect('pedidos:ver_carrito')


class CambiarEstadoPedidoView(LoginRequiredMixin, PropietarioNegocioMixin, View):
    """
    Permite al restaurante avanzar el flujo de la máquina de estados.
    Ejecuta el método clean() del modelo para aplicar las validaciones cruzadas.
    """
    def post(self, request, pk, *args, **kwargs):
        # Asegura que el pedido pertenezca al negocio del usuario autenticado
        pedido = get_object_or_404(Pedido, pk=pk, negocio__propietario=request.user)
        
        form = ActualizarEstadoPedidoForm(request.POST, instance=pedido)
        
        if form.is_valid():
            try:
                # Django corre internamente el full_clean() del modelo,disparando las alertas si intentan pasar a "En camino" sin repartidor.
                form.save()
                messages.success(request, f"El pedido #{pedido.id} cambió a: {pedido.get_estado_display()}.")
            except ValidationError as e:
                error_msg = ", '.join(e.messages)" if hasattr(e, 'messages') else str(e)
                messages.error(request, f"No se pudo actualizar el estado: {error_msg}")
        else:
            messages.error(request, "El estado enviado no es válido.")

        return redirect('pedidos:panel_negocio')