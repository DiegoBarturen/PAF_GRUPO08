from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from config.choices import EstadoPedido

from .models import AsignacionPedido, HistorialEntrega, PerfilRepartidor


def _render_repartidor_only(request, template_name, context):
    if getattr(request.user, "rol", None) != "repartidor":
        return render(request, template_name, {"acceso_denegado": True})
    return render(request, template_name, context)


def _decorar_evento_historial(evento):
    observacion = (evento.observacion or "").strip()

    if not observacion:
        evento.observacion_resumida = "Sin observacion manual"
    elif "Asignacion automatica generada por el sistema" in observacion:
        evento.observacion_resumida = "Asignacion automatica del sistema"
    elif "Asignacion activa reconstruida automaticamente" in observacion:
        evento.observacion_resumida = "Asignacion recuperada para continuar la ruta"
    else:
        evento.observacion_resumida = observacion

    if evento.evento == HistorialEntrega.EventoEntrega.ENTREGADO:
        evento.badge_class = "event-badge delivered"
    elif evento.evento == HistorialEntrega.EventoEntrega.RECOGIDO:
        evento.badge_class = "event-badge picked"
    else:
        evento.badge_class = "event-badge assigned"

    return evento


@login_required
def panel_repartidor_activo_view(request):
    asignacion = (
        AsignacionPedido.objects.select_related(
            "pedido",
            "pedido__cliente",
            "pedido__sede",
            "pedido__sede__negocio",
            "repartidor",
        )
        .filter(repartidor=request.user, activa=True)
        .first()
    )

    context = {
        "asignacion": asignacion,
        "pedido": asignacion.pedido if asignacion else None,
        "perfil_repartidor": getattr(request.user, "perfil_repartidor", None),
        "estado_listo_recojo": EstadoPedido.LISTO_RECOJO,
        "estado_en_camino": EstadoPedido.EN_CAMINO,
    }
    return _render_repartidor_only(request, "logistica/mi_pedido_activo.html", context)


@login_required
def historial_repartidor_view(request):
    historial_qs = (
        HistorialEntrega.objects.select_related("pedido", "pedido__cliente", "pedido__sede", "pedido__sede__negocio")
        .filter(repartidor=request.user)
        .order_by("-fecha")
    )
    historial = [_decorar_evento_historial(item) for item in historial_qs]
    context = {
        "historial": historial,
        "perfil_repartidor": getattr(request.user, "perfil_repartidor", None),
    }
    return _render_repartidor_only(request, "logistica/mi_historial.html", context)


@login_required
def detalle_evento_historial_view(request, evento_id):
    evento = get_object_or_404(
        HistorialEntrega.objects.select_related("pedido", "pedido__cliente", "pedido__sede", "pedido__sede__negocio", "repartidor"),
        pk=evento_id,
        repartidor=request.user,
    )
    evento = _decorar_evento_historial(evento)
    timeline = [
        _decorar_evento_historial(item)
        for item in HistorialEntrega.objects.select_related("pedido", "pedido__cliente", "pedido__sede", "pedido__sede__negocio")
        .filter(pedido=evento.pedido, repartidor=request.user)
        .order_by("-fecha")
    ]
    context = {
        "evento": evento,
        "timeline": timeline,
        "perfil_repartidor": getattr(request.user, "perfil_repartidor", None),
    }
    return _render_repartidor_only(request, "logistica/detalle_evento.html", context)


@login_required
def perfil_repartidor_view(request):
    perfil, _ = PerfilRepartidor.objects.get_or_create(usuario=request.user)
    asignacion_activa = (
        AsignacionPedido.objects.select_related("pedido")
        .filter(repartidor=request.user, activa=True)
        .first()
    )
    
    # Calcular ganancias acumuladas del costo de envío de pedidos entregados
    from django.db.models import Sum
    ganancias_dict = AsignacionPedido.objects.filter(
        repartidor=request.user,
        pedido__estado=EstadoPedido.ENTREGADO
    ).aggregate(total=Sum('pedido__costo_envio'))
    
    total_ganancias = ganancias_dict['total'] or 0.0

    context = {
        "perfil_repartidor": perfil,
        "pedido_activo": asignacion_activa.pedido if asignacion_activa else None,
        "total_asignaciones": AsignacionPedido.objects.filter(repartidor=request.user).count(),
        "total_entregas_completadas": HistorialEntrega.objects.filter(
            repartidor=request.user,
            evento=HistorialEntrega.EventoEntrega.ENTREGADO,
        ).count(),
        "total_eventos": HistorialEntrega.objects.filter(repartidor=request.user).count(),
        "total_ganancias": total_ganancias,
    }
    return _render_repartidor_only(request, "logistica/mi_perfil.html", context)


from django.shortcuts import redirect
from pedidos.models import Pedido
from django.contrib import messages
from django.db import transaction

@login_required
def solicitudes_disponibles_view(request):
    # Obtener pedidos LISTO_RECOJO sin asignación activa
    asignaciones_activas_ids = AsignacionPedido.objects.filter(activa=True).values_list('pedido_id', flat=True)
    solicitudes = Pedido.objects.select_related("sede", "sede__negocio", "cliente").filter(
        estado=EstadoPedido.LISTO_RECOJO
    ).exclude(
        id__in=asignaciones_activas_ids
    ).order_by("fecha_creacion")
    
    context = {
        "solicitudes": solicitudes,
        "perfil_repartidor": getattr(request.user, "perfil_repartidor", None),
    }
    return _render_repartidor_only(request, "logistica/solicitudes_disponibles.html", context)


@login_required
@transaction.atomic
def aceptar_solicitud_view(request, pedido_id):
    if request.method != "POST":
        return redirect("logistica:solicitudes_disponibles")
        
    if getattr(request.user, "rol", None) != "repartidor":
        return redirect("dashboard_inicio")

    # Validar si el repartidor ya tiene un pedido activo
    if AsignacionPedido.objects.filter(repartidor=request.user, activa=True).exists():
        messages.error(request, "Ya tienes un pedido activo. Debes completarlo antes de aceptar otro.")
        return redirect("logistica:solicitudes_disponibles")

    pedido = get_object_or_404(Pedido.objects.select_for_update(), id=pedido_id, estado=EstadoPedido.LISTO_RECOJO)
    
    # Validar si el pedido sigue disponible
    if AsignacionPedido.objects.filter(pedido=pedido, activa=True).exists():
        messages.error(request, "Este pedido ya fue aceptado por otro repartidor.")
        return redirect("logistica:solicitudes_disponibles")
        
    # Asignar pedido al repartidor
    pedido.repartidor = request.user
    pedido.save(update_fields=["repartidor", "fecha_actualizacion"])
    
    AsignacionPedido.objects.create(
        pedido=pedido,
        repartidor=request.user,
    )
    
    HistorialEntrega.objects.create(
        pedido=pedido,
        repartidor=request.user,
        evento=HistorialEntrega.EventoEntrega.ASIGNADO,
        observacion="El repartidor aceptó la solicitud manualmente."
    )
    
    messages.success(request, f"¡Has aceptado el pedido #{pedido.id} exitosamente!")
    return redirect("logistica:mi_pedido_activo")
