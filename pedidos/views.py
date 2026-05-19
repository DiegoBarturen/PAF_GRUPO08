# pedidos/views.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, View

from catalogo.models import Producto
from pedidos.forms import ActualizarEstadoPedidoForm, CrearPedidoForm
from pedidos.models import ItemPedido, Pedido


class PropietarioNegocioMixin(UserPassesTestMixin):
    """
    Garantiza que el usuario logueado pertenezca al rol del negocio.
    """

    def test_func(self):
        return self.request.user.is_authenticated and getattr(self.request.user, "es_negocio", False)


class HistorialPedidosClienteListView(LoginRequiredMixin, ListView):
    """
    Lista los pedidos del cliente autenticado.
    """

    model = Pedido
    template_name = "pedidos/historial_cliente.html"
    context_object_name = "pedidos"
    paginate_by = 15

    def get_queryset(self):
        return (
            Pedido.objects.filter(cliente=self.request.user)
            .select_related("negocio")
            .order_by("-fecha_creacion")
        )


class PanelNegocioPedidoListView(LoginRequiredMixin, PropietarioNegocioMixin, ListView):
    """
    Panel de control donde el restaurante gestiona sus órdenes entrantes.
    """

    model = Pedido
    template_name = "pedidos/panel_negocio.html"
    context_object_name = "pedidos"
    paginate_by = 15

    def get_queryset(self):
        return (
            Pedido.objects.filter(negocio__propietario=self.request.user)
            .select_related("cliente")
            .prefetch_related("items_pedido__producto")
            .order_by("-fecha_creacion")
        )


class CambiarEstadoPedidoView(LoginRequiredMixin, PropietarioNegocioMixin, View):
    """
    Permite al restaurante avanzar el flujo de estados del pedido.
    """

    def post(self, request, pk, *args, **kwargs):
        pedido = get_object_or_404(Pedido, pk=pk, negocio__propietario=request.user)
        form = ActualizarEstadoPedidoForm(request.POST, instance=pedido)

        if form.is_valid():
            try:
                form.save()
                messages.success(request, f"El pedido #{pedido.id} cambió a: {pedido.get_estado_display()}.")
            except ValidationError as e:
                error_msg = ", ".join(e.messages) if hasattr(e, "messages") else str(e)
                messages.error(request, f"No se pudo actualizar el estado: {error_msg}")
        else:
            messages.error(request, "El estado enviado no es válido.")

        return redirect("pedidos:panel_negocio")


def _carrito_session(request):
    carrito = request.session.get("carrito")
    if carrito is None:
        carrito = {}
        request.session["carrito"] = carrito
    return carrito


def _clear_carrito_session(request):
    request.session["carrito"] = {}
    request.session.pop("carrito", None)
    request.session.modified = True
    request.session.save()


def _producto_referencia_carrito(carrito):
    primer_item = next(iter(carrito.values()), None)
    if not primer_item:
        return None
    return (
        Producto.objects.filter(id=primer_item["producto_id"])
        .select_related("negocio")
        .first()
    )


def _build_carrito_context(request, form=None):
    carrito_sesion = request.session.get("carrito", {})
    items_carrito = []
    total_carrito = 0
    negocio_carrito = None
    productos_sugeridos = []
    productos_en_carrito_ids = []

    for datos in carrito_sesion.values():
        try:
            producto = Producto.objects.select_related("negocio", "categoria").get(id=datos["producto_id"])
        except Producto.DoesNotExist:
            continue

        subtotal = producto.precio * datos["cantidad"]
        total_carrito += subtotal

        if negocio_carrito is None:
            negocio_carrito = producto.negocio

        productos_en_carrito_ids.append(producto.id)

        items_carrito.append(
            {
                "producto": producto,
                "cantidad": datos["cantidad"],
                "subtotal": subtotal,
            }
        )

    if form is None:
        form = CrearPedidoForm(telefono_inicial=getattr(request.user, "telefono", "") or "")

    if carrito_sesion and not items_carrito:
        _clear_carrito_session(request)

    if negocio_carrito is not None:
        productos_sugeridos = list(
            Producto.objects.filter(
                negocio_id=negocio_carrito.id,
                disponible=True,
            )
            .exclude(id__in=productos_en_carrito_ids)
            .select_related("categoria", "negocio")
            .order_by("?")[:3]
        )

    return {
        "items_carrito": items_carrito,
        "total_carrito": total_carrito,
        "form": form,
        "negocio_carrito": negocio_carrito,
        "productos_sugeridos": productos_sugeridos,
    }


@login_required
def agregar_al_carrito(request, producto_id):
    """
    Guarda un producto en la sesión del carrito.
    """

    if request.method != "POST":
        return redirect("home_negocios")

    producto = get_object_or_404(Producto.objects.select_related("negocio"), id=producto_id)

    try:
        cantidad = int(request.POST.get("cantidad", 1))
    except (TypeError, ValueError):
        messages.error(request, "La cantidad enviada no es válida.")
        return redirect(request.META.get("HTTP_REFERER", reverse_lazy("home_negocios")))

    if cantidad <= 0:
        messages.error(request, "La cantidad debe ser mayor a cero.")
        return redirect(request.META.get("HTTP_REFERER", reverse_lazy("home_negocios")))

    if producto.stock < cantidad:
        messages.error(request, f"Lo sentimos, solo quedan {producto.stock} unidades de {producto.nombre}.")
        return redirect(request.META.get("HTTP_REFERER", reverse_lazy("home_negocios")))

    carrito = _carrito_session(request)
    producto_actual = _producto_referencia_carrito(carrito)
    str_id = str(producto_id)

    if producto_actual and producto_actual.negocio_id != producto.negocio_id:
        messages.error(request, "Solo puedes agregar productos de un negocio a la vez en el carrito.")
        return redirect(request.META.get("HTTP_REFERER", reverse_lazy("home_negocios")))

    if str_id in carrito:
        nueva_cantidad = carrito[str_id]["cantidad"] + cantidad
        if producto.stock < nueva_cantidad:
            messages.error(request, f"No puedes agregar más unidades. Stock máximo alcanzado para {producto.nombre}.")
            return redirect("pedidos:ver_carrito")
        carrito[str_id]["cantidad"] = nueva_cantidad
    else:
        carrito[str_id] = {
            "producto_id": producto.id,
            "cantidad": cantidad,
        }

    request.session.modified = True
    messages.success(request, f"{producto.nombre} agregado al carrito con éxito.")
    return redirect(request.META.get("HTTP_REFERER", reverse_lazy("home_negocios")))


@login_required
def actualizar_cantidad_carrito(request, producto_id):
    """
    Actualiza la cantidad de un producto dentro del carrito en sesión.
    """

    if request.method != "POST":
        return redirect("pedidos:ver_carrito")

    carrito = _carrito_session(request)
    str_id = str(producto_id)

    if str_id not in carrito:
        messages.error(request, "El producto no está en el carrito.")
        return redirect("pedidos:ver_carrito")

    try:
        cantidad = int(request.POST.get("cantidad", 1))
    except (TypeError, ValueError):
        messages.error(request, "La cantidad enviada no es válida.")
        return redirect("pedidos:ver_carrito")

    if cantidad <= 0:
        del carrito[str_id]
        request.session.modified = True
        messages.success(request, "Producto retirado del carrito.")
        return redirect("pedidos:ver_carrito")

    producto = get_object_or_404(Producto, id=producto_id)
    if cantidad > producto.stock:
        messages.error(request, f"Stock insuficiente para {producto.nombre}. Solo quedan {producto.stock} unidades.")
        return redirect("pedidos:ver_carrito")

    carrito[str_id]["cantidad"] = cantidad
    request.session.modified = True
    messages.success(request, f"Cantidad actualizada para {producto.nombre}.")
    return redirect("pedidos:ver_carrito")


@login_required
def ver_carrito(request):
    """
    Renderiza la página del carrito y el formulario de checkout.
    """

    return render(request, "pedidos/carrito.html", _build_carrito_context(request))


@login_required
def eliminar_del_carrito(request, producto_id):
    """
    Elimina un ítem específico del carrito en la sesión.
    """

    carrito = request.session.get("carrito", {})
    str_id = str(producto_id)

    if str_id in carrito:
        del carrito[str_id]
        request.session.modified = True
        messages.success(request, "Producto retirado del carrito.")

    return redirect("pedidos:ver_carrito")


class ProcesarCarritoView(LoginRequiredMixin, View):
    """
    Procesa los productos del carrito, descuenta stock y crea el pedido.
    """

    def post(self, request, *args, **kwargs):
        telefono_default = getattr(request.user, "telefono", "") or ""
        form = CrearPedidoForm(request.POST, telefono_inicial=telefono_default)
        carrito = request.session.get("carrito", {})

        if not carrito:
            messages.error(request, "No puedes procesar un pedido con el carrito vacío.")
            return redirect("pedidos:ver_carrito")

        if not form.is_valid():
            messages.error(request, "Revisa los datos del formulario antes de confirmar el pedido.")
            return render(request, "pedidos/carrito.html", _build_carrito_context(request, form=form))

        try:
            productos_carrito = []
            negocio_id = None

            for datos_item in carrito.values():
                producto = Producto.objects.select_related("negocio").get(id=datos_item["producto_id"])
                cantidad = int(datos_item["cantidad"])
                productos_carrito.append((producto, cantidad))

                if negocio_id is None:
                    negocio_id = producto.negocio_id
                elif negocio_id != producto.negocio_id:
                    raise ValidationError("El carrito contiene productos de distintos negocios.")

            if not productos_carrito:
                raise ValidationError("No se encontraron productos válidos en el carrito.")

            with transaction.atomic():
                pedido = form.save(commit=False)
                pedido.cliente = request.user
                pedido.negocio = productos_carrito[0][0].negocio
                pedido.telefono = form.cleaned_data.get("telefono") or telefono_default
                pedido.metodo_pago = form.cleaned_data["metodo_pago"]
                pedido.save()

                for producto_base, cantidad in productos_carrito:
                    producto = Producto.objects.select_for_update().get(id=producto_base.id)

                    if producto.stock < cantidad:
                        raise ValidationError(f"Stock insuficiente para el producto: {producto.nombre}")

                    producto.stock -= cantidad
                    producto.save()

                    ItemPedido.objects.create(
                        pedido=pedido,
                        producto=producto,
                        cantidad=cantidad,
                        precio_unitario=producto.precio,
                    )

            messages.success(request, f"¡Tu pedido #{pedido.id} ha sido recibido con éxito!")
            _clear_carrito_session(request)
            return redirect("pedidos:historial_cliente")

        except Producto.DoesNotExist:
            messages.error(request, "Uno de los productos del carrito ya no existe.")
            return redirect("pedidos:ver_carrito")

        except ValidationError as e:
            mensaje = ", ".join(e.messages) if hasattr(e, "messages") else str(e)
            messages.error(request, f"Error al procesar el pedido: {mensaje}")
            return render(request, "pedidos/carrito.html", _build_carrito_context(request, form=form))

        except Exception as e:
            messages.error(request, f"Ocurrió un error inesperado en el servidor: {str(e)}")
            return render(request, "pedidos/carrito.html", _build_carrito_context(request, form=form))
