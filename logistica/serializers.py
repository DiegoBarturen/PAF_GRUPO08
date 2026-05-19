from rest_framework import serializers

from .models import HistorialEntrega, PerfilRepartidor


class ActualizarUbicacionSerializer(serializers.Serializer):
    latitud = serializers.DecimalField(max_digits=9, decimal_places=6)
    longitud = serializers.DecimalField(max_digits=9, decimal_places=6)


class EstadoPedidoLogisticoSerializer(serializers.Serializer):
    observacion = serializers.CharField(required=False, allow_blank=True)


class PerfilRepartidorSerializer(serializers.Serializer):
    usuario_id = serializers.IntegerField(source="usuario.id", read_only=True)
    username = serializers.CharField(source="usuario.username", read_only=True)
    estado_actual = serializers.CharField()
    estado_actual_display = serializers.CharField(source="get_estado_actual_display", read_only=True)
    vehiculo = serializers.CharField(allow_blank=True, required=False)
    latitud = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True, required=False)
    longitud = serializers.DecimalField(max_digits=9, decimal_places=6, allow_null=True, required=False)
    ultima_actualizacion_ubicacion = serializers.DateTimeField(allow_null=True, read_only=True)


class ActualizarPerfilRepartidorSerializer(serializers.Serializer):
    estado_actual = serializers.ChoiceField(
        choices=(
            PerfilRepartidor.EstadoActual.DISPONIBLE,
            PerfilRepartidor.EstadoActual.INACTIVO,
        ),
        required=False,
    )
    vehiculo = serializers.CharField(max_length=100, required=False, allow_blank=True)


class PedidoActivoSerializer(serializers.Serializer):
    pedido_id = serializers.IntegerField(source="pedido.id")
    estado = serializers.CharField(source="pedido.estado")
    estado_display = serializers.CharField(source="pedido.get_estado_display")
    cliente = serializers.CharField(source="pedido.cliente.username")
    direccion_entrega = serializers.CharField(source="pedido.direccion_entrega")
    observaciones = serializers.CharField(source="pedido.observaciones", allow_blank=True, allow_null=True)
    total = serializers.DecimalField(source="pedido.total", max_digits=10, decimal_places=2)
    negocio = serializers.CharField(source="pedido.negocio.nombre_comercial")
    direccion_negocio = serializers.CharField(source="pedido.negocio.direccion")
    asignado_en = serializers.DateTimeField()
    recogido_en = serializers.DateTimeField(allow_null=True)


class HistorialEntregaSerializer(serializers.ModelSerializer):
    pedido_id = serializers.IntegerField(source="pedido.id", read_only=True)
    repartidor = serializers.CharField(source="repartidor.username", read_only=True)
    evento_display = serializers.CharField(source="get_evento_display", read_only=True)

    class Meta:
        model = HistorialEntrega
        fields = (
            "id",
            "pedido_id",
            "repartidor",
            "evento",
            "evento_display",
            "observacion",
            "fecha",
        )


class ResumenOperativoSerializer(serializers.Serializer):
    repartidor = serializers.CharField()
    estado_actual = serializers.CharField()
    vehiculo = serializers.CharField(allow_blank=True)
    pedido_activo_id = serializers.IntegerField(allow_null=True)
    total_asignaciones = serializers.IntegerField()
    total_entregas_completadas = serializers.IntegerField()
    total_historial_eventos = serializers.IntegerField()
