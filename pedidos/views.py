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
    
    
def agregar_al_carrito(request, producto_id):
    """
    Vista tradicional que guarda un producto en la sesión de Django.
    No toca PostgreSQL todavía.
    """
    producto = get_object_or_404(Producto, id=producto_id)
    cantidad = int(request.POST.get('cantidad', 1))
    
    if producto.stock < cantidad:
        messages.error(request, f"Lo sentimos, solo quedan {producto.stock} unidades de {producto.nombre}.")
        return redirect(request.meta.get('HTTP_REFERER', 'catalogo:lista_productos'))

    if 'carrito' not in request.session:
        request.session['carrito'] = {}
        
    carrito = request.session['carrito']
    str_id = str(producto_id)

    if str_id in carrito:
        nueva_cantidad = carrito[str_id]['cantidad'] + cantidad
        if producto.stock < nueva_cantidad:
            messages.error(request, f"No puedes agregar más unidades. Stock máximo alcanzado.")
            return redirect('pedidos:ver_carrito')
        carrito[str_id]['cantidad'] = nueva_cantidad
    else:
        carrito[str_id] = {
            'producto_id': producto.id,
            'cantidad': cantidad
        }
        
    request.session.modified = True
    messages.success(request, f"{producto.nombre} agregado al carrito con éxito.")
    return redirect(request.meta.get('HTTP_REFERER', 'catalogo:lista_productos'))


@login_required
def ver_carrito(request):
    """
    Renderiza la página del carrito recuperando los datos en tiempo real 
    de los productos almacenados en la sesión. Incluye el formulario para procesar la compra.
    """
    carrito_sesion = request.session.get('carrito', {})
    items_carrito = []
    total_carrito = 0

    for str_id, datos in carrito_sesion.items():
        try:
            producto = Producto.objects.get(id=datos['producto_id'])
            subtotal = producto.precio * datos['cantidad']
            total_carrito += subtotal
            
            items_carrito.append({
                'producto': producto,
                'cantidad': datos['cantidad'],
                'subtotal': subtotal
            })
        except Producto.DoesNotExist:
            continue

    # Instanciamos el formulario de creación de pedido para que se pueda pintar en el HTML del carrito
    form = CrearPedidoForm()

    context = {
        'items_carrito': items_carrito,
        'total_carrito': total_carrito,
        'form': form
    }
    return render(request, 'pedidos/carrito.html', context)


def eliminar_del_carrito(request, producto_id):
    """
    Elimina un ítem específico del carrito en la sesión.
    """
    carrito = request.session.get('carrito', {})
    str_id = str(producto_id)
    
    if str_id in carrito:
        del carrito[str_id]
        request.session.modified = True
        messages.success(request, "Producto retirado del carrito.")
        
    return redirect('pedidos:ver_carrito')


# =========================================================================
# CIERRE Y PROCESAMIENTO DEL CARRITO (PERSISTENCIA ACID EN BD)
# =========================================================================

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