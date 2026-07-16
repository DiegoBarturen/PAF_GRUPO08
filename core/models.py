from django.db import models
from django.conf import settings

class ManagerActivos(models.Manager):
    def get_queryset(self): 
        return super().get_queryset().filter(activo=True)

class ModeloBase(models.Model):
    creado_en = models.DateTimeField(auto_now_add=True, null=True)
    actualizado_en = models.DateTimeField(auto_now=True, null=True)
    creado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        related_name="+", on_delete=models.SET_NULL
    )
    activo = models.BooleanField(default=True, db_index=True)
    
    objects = models.Manager() # todos los registros
    activos = ManagerActivos() # solo activos
    
    def eliminar(self, usuario=None):
        """Soft delete: nunca borrar físicamente."""
        self.activo = False
        if usuario: 
            self.creado_por = usuario
        self.save(update_fields=["activo", "actualizado_en"])
        
    class Meta:
        abstract = True
