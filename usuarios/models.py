from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuario(AbstractUser):
    # Definimos los roles según el documento del proyecto
    ROLES = (
        ('cliente', 'Cliente'),
        ('negocio', 'Negocio / Vendedor'),
        ('repartidor', 'Repartidor'),
        ('admin', 'Super Admin'),
    )
    
    rol = models.CharField(max_length=20, choices=ROLES, default='cliente')
    telefono = models.CharField(max_length=15, blank=True, null=True)
    direccion = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.username} - {self.get_rol_display()}"
