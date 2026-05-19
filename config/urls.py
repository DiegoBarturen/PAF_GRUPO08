from django.contrib import admin
from django.urls import path, include
from usuarios.views import home_view
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static 


urlpatterns = [
    path('', home_view, name='home'),
    path('admin/', admin.site.urls),
    path('usuarios/', include('usuarios.urls')),
    path('api/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('dashboard/', include('dashboard.urls')),
    path('', include('catalogo.urls')),
    path('api/catalogo/', include('catalogo.urls')),
<<<<<<< HEAD
=======
    path('pedidos/', include('pedidos.urls')),
    path('', include(('logistica.urls', 'logistica'), namespace='logistica')),
>>>>>>> d37fc40967e944aa5d13f7d041562a1b4dfc63e8
]


if settings.DEBUG:
<<<<<<< HEAD
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
=======
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
>>>>>>> d37fc40967e944aa5d13f7d041562a1b4dfc63e8
