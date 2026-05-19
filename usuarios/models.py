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

    def __str__(self):
        return f"{self.username} - {self.get_rol_display()}"

    # ATAJOS DE ROL (Soluciona inconsistencias y asegura las vistas)
    @property
    def es_cliente(self):
        return self.rol == 'cliente'

    @property
    def es_negocio(self):
        return self.rol == 'negocio'

    @property
    def es_repartidor(self):
        return self.rol == 'repartidor'

    @property
    def es_admin(self):
        return self.rol == 'admin' or self.is_superuser
