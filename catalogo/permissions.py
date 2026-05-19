from rest_framework import permissions

class IsPropietarioOrReadOnly(permissions.BasePermission):
    """
    Permite lectura a cualquier usuario autenticado, 
    pero solo el dueño del negocio puede editar o borrar.
    """
    def has_object_permission(self, request, view, obj):
       
        if request.method in permissions.SAFE_METHODS:
            return True
            
       
        if hasattr(obj, 'negocio'):
            return obj.negocio.propietario == request.user
            
      
        if hasattr(obj, 'propietario'):
            return obj.propietario == request.user
            
        return False