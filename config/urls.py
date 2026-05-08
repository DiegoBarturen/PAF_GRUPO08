from django.contrib import admin
from django.urls import path, include
from usuarios.views import home_view 

urlpatterns = [
    path('', home_view, name='home'),
    path('admin/', admin.site.urls),
    path('usuarios/', include('usuarios.urls')),
]
