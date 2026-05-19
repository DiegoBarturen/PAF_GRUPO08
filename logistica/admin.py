from django.contrib import admin

from .models import AsignacionPedido, HistorialEntrega, PerfilRepartidor


@admin.register(PerfilRepartidor)
class PerfilRepartidorAdmin(admin.ModelAdmin):
    list_display = (
        "usuario",
        "estado_actual",
        "vehiculo",
        "latitud",
        "longitud",
        "ultima_actualizacion_ubicacion",
    )
    list_filter = ("estado_actual",)
    search_fields = ("usuario__username", "usuario__email", "vehiculo")


@admin.register(AsignacionPedido)
class AsignacionPedidoAdmin(admin.ModelAdmin):
    list_display = (
        "pedido",
        "repartidor",
        "activa",
        "asignado_en",
        "recogido_en",
        "entregado_en",
    )
    list_filter = ("activa", "asignado_en", "recogido_en", "entregado_en")
    search_fields = ("pedido__id", "repartidor__username")


@admin.register(HistorialEntrega)
class HistorialEntregaAdmin(admin.ModelAdmin):
    list_display = ("pedido", "repartidor", "evento", "fecha")
    list_filter = ("evento", "fecha")
    search_fields = ("pedido__id", "repartidor__username", "observacion")
