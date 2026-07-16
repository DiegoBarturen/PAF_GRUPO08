from django.contrib import admin
from pedidos.models import Pedido, ItemPedido

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'cliente', 'sede', 'estado', 'total', 'fecha_creacion')
    list_filter = ('estado', 'fecha_creacion')

admin.site.register(ItemPedido)
