from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'categorias', views.CategoriaViewSet)
router.register(r'negocios', views.NegocioViewSet)
router.register(r'productos', views.ProductoViewSet)

urlpatterns = [
    # 1. PÁGINAS HTML DEL FRONTEND (Django las lee primero de arriba a abajo)
    path('vitrina/', views.catalogo_vista, name='catalogo_vitrina'),
    path('negocios/nuevo/', views.registrar_negocio, name='registrar_negocio'),
    path('productos/admin/', views.administrar_productos, name='administrar_productos'),
    path('productos/nuevo/', views.guardar_producto, name='crear_producto'),
    path('productos/editar/<int:id>/', views.guardar_producto, name='editar_producto'),
    path('productos/eliminar/<int:id>/', views.eliminar_producto, name='eliminar_producto'),
    path('productos/disponibilidad/<int:id>/', views.cambiar_disponibilidad, name='cambiar_disponibilidad'),
    path('home/', views.home_negocios, name='home_negocios'),
    path('negocio/<int:negocio_id>/', views.detalle_negocio, name='detalle_negocio'),
    # 2. API REST (Se queda al final para que no interfiera con las páginas HTML)
    path('', include(router.urls)),
]
