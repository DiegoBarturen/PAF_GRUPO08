from django.urls import path
from . import views


urlpatterns = [
    path('', views.dashboard_inicio, name='dashboard_inicio'),
    path('exportar/', views.exportar_reporte_usuarios, name='exportar_reporte'),
]