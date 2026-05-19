from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from config.choices import EstadoPedido

from .models import AsignacionPedido, HistorialEntrega, PerfilRepartidor


def _render_repartidor_only(request, template_name, context):
    if getattr(request.user, "rol", None) != "repartidor":
        return render(request, template_name, {"acceso_denegado": True})
    return render(request, template_name, context)


@login_required
def panel_repartidor_activo_view(request):
    asignacion = (
        AsignacionPedido.objects.select_related(
            "pedido",
            "pedido__cliente",
            "pedido__negocio",
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
    historial = (
        HistorialEntrega.objects.select_related("pedido", "pedido__cliente", "pedido__negocio")
        .filter(repartidor=request.user)
        .order_by("-fecha")
    )
    context = {
        "historial": historial,
        "perfil_repartidor": getattr(request.user, "perfil_repartidor", None),
    }
    return _render_repartidor_only(request, "logistica/mi_historial.html", context)


@login_required
def perfil_repartidor_view(request):
    perfil, _ = PerfilRepartidor.objects.get_or_create(usuario=request.user)
    asignacion_activa = (
        AsignacionPedido.objects.select_related("pedido")
        .filter(repartidor=request.user, activa=True)
        .first()
    )
    context = {
        "perfil_repartidor": perfil,
        "pedido_activo": asignacion_activa.pedido if asignacion_activa else None,
        "total_asignaciones": AsignacionPedido.objects.filter(repartidor=request.user).count(),
        "total_entregas_completadas": HistorialEntrega.objects.filter(
            repartidor=request.user,
            evento=HistorialEntrega.EventoEntrega.ENTREGADO,
        ).count(),
        "total_eventos": HistorialEntrega.objects.filter(repartidor=request.user).count(),
    }
    return _render_repartidor_only(request, "logistica/mi_perfil.html", context)
