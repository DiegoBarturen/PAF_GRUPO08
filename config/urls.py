from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static 
from django.views.generic import TemplateView
# Importamos la vista del catálogo directamente
from catalogo.views import catalogo_vista 
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [
    # 1. LA RAÍZ AHORA APUNTA DIRECTAMENTE AL CATÁLOGO MINIMALISTA
    path('', catalogo_vista, name='home'),
    
    path('admin/', admin.site.urls),
    path('usuarios/', include('usuarios.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('pedidos/', include('pedidos.urls')),
    
    # Rutas de las aplicaciones
    path('catalogo/', include('catalogo.urls')), 
    path('logistica/', include(('logistica.urls', 'logistica'), namespace='logistica')),
    
    # API
    path('api/catalogo/', include('catalogo.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    
    # Páginas de Información (Footer)
    path('quienes-somos/', TemplateView.as_view(template_name='pages/quienes_somos.html'), name='quienes_somos'),
    path('contactanos/', TemplateView.as_view(template_name='pages/contactanos.html'), name='contactanos'),
    path('terminos-y-condiciones/', TemplateView.as_view(template_name='pages/terminos.html'), name='terminos'),
    path('politica-de-privacidad/', TemplateView.as_view(template_name='pages/privacidad.html'), name='privacidad'),
    path('soporte/negocios/', TemplateView.as_view(template_name='pages/soporte_negocios.html'), name='soporte_negocios'),
    path('soporte/repartidores/', TemplateView.as_view(template_name='pages/soporte_repartidores.html'), name='soporte_repartidores'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)