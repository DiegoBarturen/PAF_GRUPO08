from django.shortcuts import redirect
from django.urls import resolve, Resolver404
from django.contrib import messages
from catalogo.models import Negocio

class NegocioProfileRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, 'rol', None) == 'negocio':
            from usuarios.views import obtener_sedes_usuario
            sedes = obtener_sedes_usuario(request.user)
            
            allowed_url_names = [
                'registrar_negocio',
                'seleccionar_sede',
                'logout',
            ]
            
            try:
                resolver_match = resolve(request.path_info)
                current_url_name = resolver_match.url_name
            except Resolver404:
                current_url_name = None
            
            path = request.path
            is_exempt = (
                current_url_name in allowed_url_names or 
                path.startswith('/static/') or 
                path.startswith('/media/') or
                path.startswith('/admin/')
            )

            if not is_exempt:
                # 1. Si no tiene negocio y no tiene sedes asignadas
                if not Negocio.objects.filter(propietario=request.user).exists() and not sedes.exists():
                    messages.warning(request, "Debes registrar los datos de tu establecimiento para poder acceder al resto de opciones.")
                    return redirect('registrar_negocio')
                
                # 2. Si tiene sedes pero no ha seleccionado una
                sede_id = request.session.get('sede_id')
                if not sede_id:
                    if sedes.count() == 1:
                        request.session['sede_id'] = sedes.first().id
                    elif sedes.count() > 1:
                        messages.info(request, "Por favor selecciona una sede para continuar.")
                        return redirect('seleccionar_sede')

        response = self.get_response(request)
        return response
