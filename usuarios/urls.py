from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('seleccionar-sede/', views.seleccionar_sede_view, name='seleccionar_sede'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.perfil_view, name='perfil'),
    path('reset_password/', auth_views.PasswordResetView.as_view(template_name="usuarios/password_reset.html"), name="reset_password"),
    path('reset_password_sent/', auth_views.PasswordResetDoneView.as_view(template_name="usuarios/password_reset_sent.html"), name="password_reset_done"),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(template_name="usuarios/password_reset_form.html"), name="password_reset_confirm"),
    path('reset_password_complete/', auth_views.PasswordResetCompleteView.as_view(template_name="usuarios/password_reset_done.html"), name="password_reset_complete"),
    path('api/actualizar-perfil/', views.actualizar_perfil_cliente_api, name='api_actualizar_perfil'),
]
