from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario

# Registramos el modelo personalizado
@admin.register(Usuario)
class UsuarioCustomAdmin(UserAdmin):
    # Agregamos el campo 'rol' para que sea visible al editar usuarios
    fieldsets = UserAdmin.fieldsets + (
        ('Datos Extra Delivery', {'fields': ('rol', 'telefono', 'direccion')}),
    )
    # Mostramos el rol en la lista principal
    list_display = ('username', 'email', 'rol', 'is_staff')
    list_filter = ('rol', 'is_staff', 'is_superuser', 'is_active')
