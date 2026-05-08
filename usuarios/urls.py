from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('registro/', views.registro_view, name='registro'),
    # Django ya tiene una vista lista para cerrar sesión, la aprovechamos:
    path('logout/', LogoutView.as_view(next_page='login'), name='logout'),
]