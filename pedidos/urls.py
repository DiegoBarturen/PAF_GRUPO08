# pedidos/urls.py
from django.urls import path
from pedidos.views import HistorialPedidosClienteListView, PanelNegocioPedidoListView, CambiarEstadoPedidoView

app_name = 'pedidos'

urlpatterns = [
    # Ruta para el historial de pedidos del cliente
    path('mis-pedidos/', HistorialPedidosClienteListView.as_view(), name='historial_cliente'),
    
    # Ruta para el panel de control del restaurante/negocio
    path('panel/', PanelNegocioPedidoListView.as_view(), name='panel_negocio'),
    
    # Ruta POST interna para mutar el estado del pedido
    path('pedido/<int:pk>/cambiar-estado/', CambiarEstadoPedidoView.as_view(), name='cambiar_estado'),
]