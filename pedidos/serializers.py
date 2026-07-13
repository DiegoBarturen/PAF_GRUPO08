from rest_framework import serializers
from pedidos.models import Pedido, ItemPedido
from catalogo.models import Producto

class ItemPedidoSerializer(serializers.ModelSerializer):
    """
    Serializador para las líneas de detalle del pedido.
    Incluye detalles del producto en modo lectura para el Frontend.
    """
    producto_nombre = serializers.CharField(source='producto.nombre', read_only=True)

    class Meta:
        model = ItemPedido
        fields = ['id', 'producto', 'producto_nombre', 'cantidad', 'precio_unitario']
        read_only_fields = ['precio_unitario']

class PedidoSerializer(serializers.ModelSerializer):
    """
    Serializador principal para la cabecera del Pedido.
    Usa el related_name='items' del modelo para anidar los detalles en modo lectura.
    """
    items = ItemPedidoSerializer(many=True, read_only=True)
    estado_display = serializers.CharField(source='get_estado_display', read_only=True)
    cliente_nombre = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = [
            'id', 'cliente', 'cliente_nombre', 'negocio', 'repartidor', 
            'estado', 'estado_display', 'fecha_creacion', 'total', 'items'
        ]
        read_only_fields = ['cliente', 'estado', 'total', 'fecha_creacion']

    def get_cliente_nombre(self, obj):
        """Campo calculado usando SerializerMethodField"""
        if obj.cliente:
            return obj.cliente.get_full_name() or obj.cliente.username
        return "Cliente no asignado"