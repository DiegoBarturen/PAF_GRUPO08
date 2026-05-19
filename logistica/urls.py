from django.urls import path

from .api_views import (
    ConfirmarEntregaView,
    ConfirmarRecojoView,
    ActualizarUbicacionRepartidorView,
    MiHistorialEntregasApiView,
    MiPerfilRepartidorApiView,
    MiPedidoActivoApiView,
    MiResumenOperativoApiView,
)
from .views import (
    historial_repartidor_view,
    panel_repartidor_activo_view,
    perfil_repartidor_view,
)

app_name = "logistica"

urlpatterns = [
    path(
        "logistica/mi-pedido-activo/",
        panel_repartidor_activo_view,
        name="mi_pedido_activo",
    ),
    path(
        "logistica/mi-historial/",
        historial_repartidor_view,
        name="mi_historial",
    ),
    path(
        "logistica/mi-perfil/",
        perfil_repartidor_view,
        name="mi_perfil",
    ),
    path(
        "api/repartidores/<int:repartidor_id>/ubicacion/",
        ActualizarUbicacionRepartidorView.as_view(),
        name="actualizar_ubicacion_repartidor",
    ),
    path(
        "api/logistica/mi-pedido-activo/",
        MiPedidoActivoApiView.as_view(),
        name="mi_pedido_activo_api",
    ),
    path(
        "api/logistica/mi-perfil/",
        MiPerfilRepartidorApiView.as_view(),
        name="mi_perfil_api",
    ),
    path(
        "api/logistica/mi-historial/",
        MiHistorialEntregasApiView.as_view(),
        name="mi_historial_api",
    ),
    path(
        "api/logistica/mi-resumen/",
        MiResumenOperativoApiView.as_view(),
        name="mi_resumen_api",
    ),
    path(
        "api/logistica/pedidos/<int:pedido_id>/confirmar-recojo/",
        ConfirmarRecojoView.as_view(),
        name="confirmar_recojo",
    ),
    path(
        "api/logistica/pedidos/<int:pedido_id>/confirmar-entrega/",
        ConfirmarEntregaView.as_view(),
        name="confirmar_entrega",
    ),
]
