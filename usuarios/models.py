from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuario(AbstractUser):
    ROLES = (
        ('cliente', 'Cliente'),
        ('negocio', 'Negocio / Vendedor'),
        ('repartidor', 'Repartidor'),
        ('admin', 'Super Admin'),
    )
    
    rol = models.CharField(max_length=20, choices=ROLES, default='cliente')
    telefono = models.CharField(max_length=15, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    def __str__(self):
        return f"{self.username} - {self.get_rol_display()}"

    @property
    def es_cliente(self):
        return self.rol == 'cliente' and not self.is_superuser

    @property
    def es_negocio(self):
        return self.rol == 'negocio' and not self.is_superuser

    @property
    def es_repartidor(self):
        return self.rol == 'repartidor' and not self.is_superuser

    @property
    def es_admin(self):
        return self.rol == 'admin' or self.is_superuser

class UsuarioSede(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='sedes_asignadas')
    sede = models.ForeignKey('catalogo.Sede', on_delete=models.CASCADE, related_name='usuarios_asignados')
    ROL_CHOICES = (
        ('admin_sede', 'Administrador de Sede'),
        ('trabajador', 'Trabajador / Cajero'),
    )
    rol = models.CharField(max_length=20, choices=ROL_CHOICES)
    estado = models.BooleanField(default=True)

    class Meta:
        unique_together = ('usuario', 'sede')

    def __str__(self):
        return f"{self.usuario.username} - {self.sede.nombre} ({self.get_rol_display()})"