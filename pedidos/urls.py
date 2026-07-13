# pedidos/urls.py
from django.urls import path
from pedidos import views, api_views
from pedidos.views import HistorialPedidosClienteListView, PanelNegocioPedidoListView, CambiarEstadoPedidoView

app_name = 'pedidos'

urlpatterns = [
    # Ruta para el historial de pedidos del cliente
    path('mis-pedidos/', HistorialPedidosClienteListView.as_view(), name='historial_cliente'),
    
    # Ruta para el panel de control del restaurante/negocio
    path('panel/', PanelNegocioPedidoListView.as_view(), name='panel_negocio'),
    
    # Ruta POST interna para mutar el estado del pedido
    path('pedido/<int:pk>/cambiar-estado/', CambiarEstadoPedidoView.as_view(), name='cambiar_estado'),
    path('carrito/', views.ver_carrito, name='ver_carrito'),
    path('carrito/agregar/<int:producto_id>/', views.agregar_al_carrito, name='agregar_al_carrito'),
    path('carrito/actualizar/<int:producto_id>/', views.actualizar_cantidad_carrito, name='actualizar_cantidad_carrito'),
    path('carrito/eliminar/<int:producto_id>/', views.eliminar_del_carrito, name='eliminar_del_carrito'),
    
    # Botón final de "Confirmar Compra" que descuenta stock en PostgreSQL
    path('carrito/procesar/', views.ProcesarCarritoView.as_view(), name='procesar_carrito'),
    path('carrito/aplicar-cupon/', views.aplicar_cupon, name='aplicar_cupon'),
    path('carrito/remover-cupon/', views.remover_cupon, name='remover_cupon'),
    
    # Rutas para el portal de negocios y configuración
    path('panel/actualizar-horarios/', views.ActualizarHorariosView.as_view(), name='actualizar_horarios'),
    path('panel/actualizar-promocion/', views.ActualizarPromocionView.as_view(), name='actualizar_promocion'),
    path('panel/actualizar-publicidad/', views.ActualizarPublicidadView.as_view(), name='actualizar_publicidad'),
    path('panel/exportar-reporte/', views.ExportarReporteNegocioView.as_view(), name='exportar_reporte_negocio'),
    path('pedido/valorar/', views.CrearValoracionView.as_view(), name='crear_valoracion'),
    
    #Ruta API REST
    path('api/v1/pedidos/', api_views.PedidoListCreateAPIView.as_view(), name='api_pedido_list_create'),
    path('api/v1/pedidos/<int:pk>/', api_views.PedidoDetailAPIView.as_view(), name='api_pedido_detail'), 
    path('api/v1/pedidos/<int:pk>/cambiar-estado/', api_views.CambiarEstadoPedidoAPIView.as_view(), name='api_pedido_cambiar_estado'),
]
