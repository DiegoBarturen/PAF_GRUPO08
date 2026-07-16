from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_inicio, name='dashboard_inicio'),
    path('exportar/', views.exportar_reporte_usuarios, name='exportar_reporte'),
    path('api/usuarios/<int:usuario_id>/toggle-activo/', views.toggle_usuario_activo, name='api_toggle_usuario_activo'),
    path('api/negocios/<int:negocio_id>/toggle-abierto/', views.toggle_negocio_abierto, name='api_toggle_negocio_abierto'),
    path('api/negocios/<int:negocio_id>/toggle-destacado/', views.toggle_negocio_destacado, name='api_toggle_negocio_destacado'),
]