# pedidos/views.py
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views.generic import ListView, View

from catalogo.models import Producto, Sede
from config.choices import EstadoPedido
from logistica.services import asignar_repartidor_a_pedido
from pedidos.forms import ActualizarEstadoPedidoForm, CrearPedidoForm
from pedidos.models import ItemPedido, Pedido

class PropietarioNegocioMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and getattr(self.request.user, "es_negocio", False)

class HistorialPedidosClienteListView(LoginRequiredMixin, ListView):
    model = Pedido
    template_name = "pedidos/historial_cliente.html"
    context_object_name = "pedidos"
    paginate_by = 15

    def dispatch(self, request, *args, **kwargs):
        rol = getattr(request.user, 'rol', None)
        if rol == 'negocio':
            return redirect('pedidos:panel_negocio')
        elif rol == 'repartidor':
            return redirect('logistica:mi_pedido_activo')
        elif rol == 'admin' or request.user.is_superuser:
            return redirect('dashboard_inicio')
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return (
            Pedido.objects.filter(cliente=self.request.user)
            .select_related("sede__negocio")
            .order_by("-fecha_creacion")
        )

class PanelNegocioPedidoListView(LoginRequiredMixin, PropietarioNegocioMixin, ListView):
    model = Pedido
    template_name = "pedidos/panel_negocio.html"
    context_object_name = "pedidos"
    paginate_by = 15

    def get_queryset(self):
        sede_id = self.request.session.get('sede_id')
        return (
            Pedido.objects.filter(sede_id=sede_id)
            .select_related("cliente")
            .prefetch_related("items_pedido__producto")
            .order_by("-fecha_creacion")
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from catalogo.models import Producto, Valoracion
        
        sede_id = self.request.session.get('sede_id')
        sede = Sede.objects.filter(id=sede_id).select_related('negocio').first() if sede_id else None
        
        context["sede"] = sede
        context["negocio"] = sede.negocio if sede else None
        
        context["total_completados"] = 0
        context["total_cancelados"] = 0
        context["total_activos"] = 0
        context["ingresos_estimados"] = 0.0
        context["valoracion_promedio"] = 0.0
        context["valoracion_estrellas"] = range(0)
        context["valoraciones"] = Valoracion.objects.none()
        context["productos_negocio"] = Producto.objects.none()
        
        if sede:
            todos_pedidos = Pedido.objects.filter(sede=sede)
            
            completados = todos_pedidos.filter(estado=EstadoPedido.ENTREGADO)
            cancelados = todos_pedidos.filter(estado=EstadoPedido.CANCELADO)
            
            context["total_completados"] = completados.count()
            context["total_cancelados"] = cancelados.count()
            context["total_activos"] = todos_pedidos.exclude(estado__in=[EstadoPedido.ENTREGADO, EstadoPedido.CANCELADO]).count()
            
            context["ingresos_estimados"] = sum((p.subtotal - (p.descuento or Decimal('0.00'))) for p in completados)
            
            valoraciones = Valoracion.objects.filter(sede=sede).select_related("cliente").order_by("-fecha")
            context["valoraciones"] = valoraciones
            
            if valoraciones.exists():
                promedio = sum(v.puntuacion for v in valoraciones) / valoraciones.count()
                context["valoracion_promedio"] = round(promedio, 1)
                context["valoracion_estrellas"] = range(int(promedio))
                
            context["productos_negocio"] = Producto.objects.filter(sede=sede)
            productos_bajo = Producto.objects.filter(sede=sede, stock__lt=3)
            context["productos_bajo_stock"] = productos_bajo
            if productos_bajo.exists():
                nombres = ", ".join([p.nombre for p in productos_bajo])
                messages.warning(
                    self.request, 
                    f"¡Alerta de inventario bajo! Los siguientes productos tienen menos de 3 unidades en stock: {nombres}."
                )
            
        return context

class CambiarEstadoPedidoView(LoginRequiredMixin, PropietarioNegocioMixin, View):
    def post(self, request, pk, *args, **kwargs):
        sede_id = request.session.get('sede_id')
        pedido = get_object_or_404(Pedido, pk=pk, sede_id=sede_id)
        form = ActualizarEstadoPedidoForm(request.POST, instance=pedido)

        if form.is_valid():
            try:
                pedido_actualizado = form.save()
                asignacion = None

                if pedido_actualizado.estado == EstadoPedido.LISTO_RECOJO:
                    asignacion = asignar_repartidor_a_pedido(pedido_actualizado)

                messages.success(
                    request,
                    f"El pedido #{pedido.id} cambio a: {pedido_actualizado.get_estado_display()}.",
                )

                if pedido_actualizado.estado == EstadoPedido.LISTO_RECOJO:
                    if asignacion:
                        messages.info(
                            request,
                            (
                                f"El sistema asigno automaticamente el pedido "
                                f"al repartidor {asignacion.repartidor.username}."
                            ),
                        )
                    else:
                        messages.warning(
                            request,
                            (
                                "El pedido quedo listo para recojo, pero no hay repartidores "
                                "disponibles en este momento."
                            ),
                        )
            except ValidationError as e:
                error_msg = ", ".join(e.messages) if hasattr(e, "messages") else str(e)
                messages.error(request, f"No se pudo actualizar el estado: {error_msg}")
        else:
            messages.error(request, "El estado enviado no es valido.")

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
        .select_related("sede")
        .first()
    )

def _build_carrito_context(request, form=None):
    carrito_sesion = request.session.get("carrito", {})
    items_carrito = []
    total_carrito = 0
    sede_carrito = None
    productos_sugeridos = []
    productos_en_carrito_ids = []

    for datos in list(carrito_sesion.values()):
        try:
            producto = Producto.objects.select_related("sede", "categoria").get(
                id=datos["producto_id"]
            )
        except Producto.DoesNotExist:
            continue

        if not producto.disponible or producto.stock <= 0:
            continue

        precio_a_usar = producto.precio_oferta if (producto.precio_oferta and producto.precio_oferta > 0) else producto.precio
        subtotal = float(precio_a_usar) * datos["cantidad"]
        total_carrito += subtotal

        if sede_carrito is None:
            sede_carrito = producto.sede

        productos_en_carrito_ids.append(producto.id)

        items_carrito.append(
            {
                "producto": producto,
                "cantidad": datos["cantidad"],
                "subtotal": subtotal,
            }
        )

    if form is None:
        form = CrearPedidoForm(
            telefono_inicial=getattr(request.user, "telefono", "") or "",
            initial={
                "direccion_entrega": getattr(request.user, "direccion", "") or "",
                "latitud": getattr(request.user, "latitud", None),
                "longitud": getattr(request.user, "longitud", None),
            }
        )

    if carrito_sesion and not items_carrito:
        _clear_carrito_session(request)

    if sede_carrito is not None:
        productos_sugeridos = list(
            Producto.objects.filter(
                sede_id=sede_carrito.id,
                disponible=True,
                stock__gt=0,
            )
            .exclude(id__in=productos_en_carrito_ids)
            .select_related("categoria", "sede")
            .order_by("?")[:3]
        )

    cupon_aplicado = request.session.get("cupon_aplicado")
    from decimal import Decimal
    descuento = Decimal("0.00")

    if cupon_aplicado == "NATIVO50" and request.user.is_authenticated:
        has_previous_orders = Pedido.objects.filter(cliente=request.user).exists()
        if not has_previous_orders:
            descuento = (Decimal(str(total_carrito)) * Decimal("0.25")).quantize(Decimal("0.01"))
        else:
            request.session.pop("cupon_aplicado", None)
            cupon_aplicado = None

    costo_envio = sede_carrito.costo_envio if sede_carrito else Decimal("0.00")
    total_con_envio = total_carrito - float(descuento) + float(costo_envio)

    return {
        "items_carrito": items_carrito,
        "total_carrito": total_carrito,
        "descuento": float(descuento),
        "cupon_aplicado": cupon_aplicado,
        "costo_envio": float(costo_envio),
        "total_con_envio": total_con_envio,
        "form": form,
        "negocio_carrito": sede_carrito.negocio if sede_carrito else None,
        "sede_carrito": sede_carrito,
        "productos_sugeridos": productos_sugeridos,
    }

@login_required
def agregar_al_carrito(request, producto_id):
    if request.method != "POST":
        return redirect("home_negocios")

    producto = get_object_or_404(Producto.objects.select_related("sede"), id=producto_id)

    try:
        cantidad = int(request.POST.get("cantidad", 1))
    except (TypeError, ValueError):
        messages.error(request, "La cantidad enviada no es valida.")
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

    if producto_actual and producto_actual.sede_id != producto.sede_id:
        messages.error(request, "Solo puedes agregar productos de una sede a la vez en el carrito.")
        return redirect(request.META.get("HTTP_REFERER", reverse_lazy("home_negocios")))

    if str_id in carrito:
        nueva_cantidad = carrito[str_id]["cantidad"] + cantidad
        if producto.stock < nueva_cantidad:
            messages.error(
                request,
                f"No puedes agregar mas unidades. Stock maximo alcanzado para {producto.nombre}.",
            )
            return redirect("pedidos:ver_carrito")
        carrito[str_id]["cantidad"] = nueva_cantidad
    else:
        carrito[str_id] = {
            "producto_id": producto.id,
            "cantidad": cantidad,
        }

    request.session.modified = True
    messages.success(request, f"{producto.nombre} agregado al carrito con exito.")
    return redirect(request.META.get("HTTP_REFERER", reverse_lazy("home_negocios")))

@login_required
def actualizar_cantidad_carrito(request, producto_id):
    if request.method != "POST":
        return redirect("pedidos:ver_carrito")

    carrito = _carrito_session(request)
    str_id = str(producto_id)

    if str_id not in carrito:
        messages.error(request, "El producto no esta en el carrito.")
        return redirect("pedidos:ver_carrito")

    try:
        cantidad = int(request.POST.get("cantidad", 1))
    except (TypeError, ValueError):
        messages.error(request, "La cantidad enviada no es valida.")
        return redirect("pedidos:ver_carrito")

    if cantidad <= 0:
        del carrito[str_id]
        request.session.modified = True
        messages.success(request, "Producto retirado del carrito.")
        return redirect("pedidos:ver_carrito")

    producto = get_object_or_404(Producto, id=producto_id)
    if cantidad > producto.stock:
        messages.error(
            request,
            f"Stock insuficiente para {producto.nombre}. Solo quedan {producto.stock} unidades.",
        )
        return redirect("pedidos:ver_carrito")

    carrito[str_id]["cantidad"] = cantidad
    request.session.modified = True
    messages.success(request, f"Cantidad actualizada para {producto.nombre}.")
    return redirect("pedidos:ver_carrito")

@login_required
def ver_carrito(request):
    rol = getattr(request.user, 'rol', None)
    if rol == 'negocio':
        return redirect('pedidos:panel_negocio')
    elif rol == 'repartidor':
        return redirect('logistica:mi_pedido_activo')
    elif rol == 'admin' or request.user.is_superuser:
        return redirect('dashboard_inicio')

    return render(request, "pedidos/carrito.html", _build_carrito_context(request))

@login_required
def eliminar_del_carrito(request, producto_id):
    carrito = request.session.get("carrito", {})
    str_id = str(producto_id)

    if str_id in carrito:
        del carrito[str_id]
        request.session.modified = True
        messages.success(request, "Producto retirado del carrito.")

    return redirect("pedidos:ver_carrito")

class ProcesarCarritoView(LoginRequiredMixin, View):
    def dispatch(self, request, *args, **kwargs):
        rol = getattr(request.user, 'rol', None)
        if rol == 'negocio':
            return redirect('pedidos:panel_negocio')
        elif rol == 'repartidor':
            return redirect('logistica:mi_pedido_activo')
        elif rol == 'admin' or request.user.is_superuser:
            return redirect('dashboard_inicio')
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        telefono_default = getattr(request.user, "telefono", "") or ""
        form = CrearPedidoForm(request.POST, telefono_inicial=telefono_default)
        carrito = request.session.get("carrito", {})

        if not carrito:
            messages.error(request, "No puedes procesar un pedido con el carrito vacio.")
            return redirect("pedidos:ver_carrito")

        if not form.is_valid():
            messages.error(request, "Revisa los datos del formulario antes de confirmar el pedido.")
            return render(request, "pedidos/carrito.html", _build_carrito_context(request, form=form))

        try:
            productos_carrito = []
            sede_id = None

            for datos_item in carrito.values():
                producto = Producto.objects.select_related("sede").get(id=datos_item["producto_id"])
                cantidad = int(datos_item["cantidad"])
                productos_carrito.append((producto, cantidad))

                if sede_id is None:
                    sede_id = producto.sede_id
                elif sede_id != producto.sede_id:
                    raise ValidationError("El carrito contiene productos de distintas sedes.")

            if not productos_carrito:
                raise ValidationError("No se encontraron productos validos en el carrito.")

            with transaction.atomic():
                pedido = form.save(commit=False)
                pedido.cliente = request.user
                pedido.sede = productos_carrito[0][0].sede
                pedido.telefono = form.cleaned_data.get("telefono") or telefono_default
                pedido.metodo_pago = form.cleaned_data["metodo_pago"]
                
                if not pedido.latitud or not pedido.longitud:
                    pedido.latitud = request.user.latitud
                    pedido.longitud = request.user.longitud
                
                from decimal import Decimal
                pedido.costo_envio = pedido.sede.costo_envio or Decimal("0.00")
                
                subtotal_temp = Decimal("0.00")
                for producto_base, cantidad in productos_carrito:
                    precio_a_usar = producto_base.precio_oferta if (producto_base.precio_oferta and producto_base.precio_oferta > 0) else producto_base.precio
                    subtotal_temp += Decimal(str(precio_a_usar)) * Decimal(str(cantidad))
                
                cupon_aplicado = request.session.get("cupon_aplicado")
                descuento = Decimal("0.00")
                if cupon_aplicado == "NATIVO50":
                    has_previous_orders = Pedido.objects.filter(cliente=request.user).exists()
                    if not has_previous_orders:
                        descuento = (subtotal_temp * Decimal("0.25")).quantize(Decimal("0.01"))
                        pedido.cupon = "NATIVO50"
                        pedido.descuento = descuento
                
                pedido.subtotal = subtotal_temp.quantize(Decimal("0.01"))
                pedido.total = (subtotal_temp - descuento + pedido.costo_envio).quantize(Decimal("0.01"))
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

            messages.success(request, f"Tu pedido #{pedido.id} ha sido recibido con exito.")
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
            messages.error(request, f"Ocurrio un error inesperado en el servidor: {str(e)}")
            return render(request, "pedidos/carrito.html", _build_carrito_context(request, form=form))


class ExportarReporteNegocioView(LoginRequiredMixin, PropietarioNegocioMixin, View):
    def get(self, request, *args, **kwargs):
        import csv
        from django.http import HttpResponse
        
        sede_id = request.session.get('sede_id')
        sede = get_object_or_404(Sede, id=sede_id)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="reporte_ventas_{sede.negocio.nombre_comercial}_{sede.nombre}.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['ID Pedido', 'Cliente', 'Fecha de Creacion', 'Estado', 'Subtotal', 'Costo Envio', 'Total', 'Metodo Pago'])
        
        pedidos = Pedido.objects.filter(sede=sede).order_by('-fecha_creacion')
        for p in pedidos:
            writer.writerow([
                p.id,
                p.cliente.username,
                p.fecha_creacion.strftime('%Y-%m-%d %H:%M'),
                p.get_estado_display(),
                p.subtotal,
                p.costo_envio,
                p.total,
                p.get_metodo_pago_display()
            ])
            
        return response


class ActualizarHorariosView(LoginRequiredMixin, PropietarioNegocioMixin, View):
    def post(self, request, *args, **kwargs):
        sede_id = request.session.get('sede_id')
        sede = get_object_or_404(Sede, id=sede_id)
        
        abierto = request.POST.get("abierto") == "true"
        hora_apertura = request.POST.get("hora_apertura")
        hora_cierre = request.POST.get("hora_cierre")
        
        sede.abierto = abierto
        if hora_apertura:
            sede.hora_apertura = hora_apertura
        else:
            sede.hora_apertura = None
        if hora_cierre:
            sede.hora_cierre = hora_cierre
        else:
            sede.hora_cierre = None
            
        sede.save()
        
        messages.success(request, "Configuración de horarios y estado de la sede guardada con éxito.")
        return redirect("pedidos:panel_negocio")


class ActualizarPromocionView(LoginRequiredMixin, PropietarioNegocioMixin, View):
    def post(self, request, *args, **kwargs):
        producto_id = request.POST.get("producto_id")
        descuento_porcentaje = request.POST.get("descuento_porcentaje")
        
        sede_id = request.session.get('sede_id')
        producto = get_object_or_404(Producto, pk=producto_id, sede_id=sede_id)
        
        try:
            if descuento_porcentaje and int(descuento_porcentaje) > 0:
                producto.descuento_porcentaje = int(descuento_porcentaje)
            else:
                producto.descuento_porcentaje = None
            producto.save()
            messages.success(request, f"Promoción para '{producto.nombre}' actualizada con éxito.")
        except Exception as e:
            messages.error(request, f"Error al actualizar la promoción: {str(e)}")
            
        return redirect("pedidos:panel_negocio")


class ActualizarPublicidadView(LoginRequiredMixin, PropietarioNegocioMixin, View):
    def post(self, request, *args, **kwargs):
        from catalogo.models import Negocio
        sede_id = request.session.get('sede_id')
        sede = get_object_or_404(Sede, id=sede_id)
        negocio = sede.negocio
        
        destacado = request.POST.get("destacado") == "true"
        negocio.destacado = destacado
        negocio.save()
        
        if destacado:
            messages.success(request, "¡Tu negocio ahora está patrocinado y aparecerá destacado en el catálogo!")
        else:
            messages.success(request, "Campañas de publicidad detenidas con éxito.")
        return redirect("pedidos:panel_negocio")


class CrearValoracionView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        from catalogo.models import Valoracion
        
        pedido_id = request.POST.get("pedido_id")
        puntuacion = request.POST.get("puntuacion")
        comentario = request.POST.get("comentario")
        
        pedido = get_object_or_404(Pedido, pk=pedido_id, cliente=request.user, estado=EstadoPedido.ENTREGADO)
        
        Valoracion.objects.create(
            sede=pedido.sede,
            cliente=request.user,
            puntuacion=int(puntuacion),
            comentario=comentario
        )
        
        messages.success(request, "¡Muchas gracias por tu calificación! Tu opinión ha sido enviada a la sede.")
        return redirect("pedidos:historial_cliente")


@login_required
def aplicar_cupon(request):
    if request.method == "POST":
        codigo = request.POST.get("codigo_cupon", "").strip().upper()
        if codigo == "NATIVO50":
            has_previous_orders = Pedido.objects.filter(cliente=request.user).exists()
            if not has_previous_orders:
                request.session["cupon_aplicado"] = "NATIVO50"
                messages.success(request, "¡Cupón NATIVO50 aplicado con éxito! Obtienes 25% de descuento en tus productos.")
            else:
                messages.error(request, "El cupón NATIVO50 es válido únicamente para nuevos usuarios en su primera compra.")
        else:
            messages.error(request, "Código de cupón inválido.")
    return redirect("pedidos:ver_carrito")


@login_required
def remover_cupon(request):
    request.session.pop("cupon_aplicado", None)
    messages.success(request, "Cupón removido.")
    return redirect("pedidos:ver_carrito")
