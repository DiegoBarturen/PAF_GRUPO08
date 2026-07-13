from catalogo.models import Sede

def sede_actual(request):
    if request.user.is_authenticated and getattr(request.user, 'rol', None) == 'negocio':
        sede_id = request.session.get('sede_id')
        if sede_id:
            sede = Sede.objects.filter(id=sede_id).first()
            if sede:
                return {'sede_actual': sede}
    return {}
