from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from usuarios.models import Usuario
from catalogo.models import Negocio
from pedidos.models import Pedido
import csv
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
from django.db.models import Sum
from django.views.decorators.http import require_POST

def es_admin(user):
    return user.is_authenticated and (user.rol == 'admin' or user.is_superuser)

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='home') 
def dashboard_inicio(request):
    total_usuarios = Usuario.objects.count()
    total_clientes = Usuario.objects.filter(rol='cliente').count()
    total_negocios = Usuario.objects.filter(rol='negocio').count()
    total_repartidores = Usuario.objects.filter(rol='repartidor').count()

    hoy = timezone.now().date()
    pedidos_hoy = Pedido.objects.filter(fecha_creacion__date=hoy)
    
    total_pedidos_hoy = pedidos_hoy.count()
    ingresos_hoy = pedidos_hoy.aggregate(Sum('total'))['total__sum'] or 0.00

    # Calcular ingresos históricos totales y ganancia de la empresa admin (10% sobre subtotal)
    from decimal import Decimal
    from config.choices import EstadoPedido
    
    pedidos_entregados = Pedido.objects.filter(estado=EstadoPedido.ENTREGADO)
    total_ingresos_sistema = pedidos_entregados.aggregate(Sum('total'))['total__sum'] or Decimal("0.00")
    
    subtotal_entregados = pedidos_entregados.aggregate(Sum('subtotal'))['subtotal__sum'] or Decimal("0.00")
    ganancias_empresa = (subtotal_entregados * Decimal("0.10")).quantize(Decimal("0.01"))

    # Listados para administración
    usuarios = Usuario.objects.all().order_by('-date_joined')
    negocios = Negocio.objects.all().select_related('propietario').order_by('-id')
    pedidos = Pedido.objects.all().select_related('cliente', 'negocio').order_by('-fecha_creacion')

    context = {
        'total_usuarios': total_usuarios,
        'total_clientes': total_clientes,
        'total_negocios': total_negocios,
        'total_repartidores': total_repartidores,
        'total_pedidos_hoy': total_pedidos_hoy,
        'ingresos_hoy': ingresos_hoy,
        'total_ingresos_sistema': total_ingresos_sistema,
        'ganancias_empresa': ganancias_empresa,
        'usuarios': usuarios,
        'negocios': negocios,
        'pedidos': pedidos,
    }
    
    return render(request, 'dashboard/inicio.html', context)

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='home')
def exportar_reporte_usuarios(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="reporte_usuarios_nativo.csv"'

    writer = csv.writer(response)

    writer.writerow(['ID', 'Nombre', 'Correo', 'Rol', 'Fecha de Registro'])

    usuarios = Usuario.objects.all().order_by('-date_joined') 
    
    for usuario in usuarios:
        writer.writerow([
            usuario.id,
            f"{usuario.first_name} {usuario.last_name}",
            usuario.email,
            usuario.rol.upper(), 
            usuario.date_joined.strftime('%Y-%m-%d %H:%M') 
        ])

    return response

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='home')
@require_POST
def toggle_usuario_activo(request, usuario_id):
    usuario = get_object_or_404(Usuario, id=usuario_id)
    if usuario == request.user:
        return JsonResponse({"error": "No puedes desactivarte a ti mismo."}, status=400)
    usuario.is_active = not usuario.is_active
    usuario.save()
    return JsonResponse({"is_active": usuario.is_active, "message": "Estado de usuario actualizado."})

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='home')
@require_POST
def toggle_negocio_abierto(request, negocio_id):
    negocio = get_object_or_404(Negocio, id=negocio_id)
    negocio.abierto = not negocio.abierto
    negocio.save()
    return JsonResponse({"abierto": negocio.abierto, "message": "Estado de atención de negocio actualizado."})

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='home')
@require_POST
def toggle_negocio_destacado(request, negocio_id):
    negocio = get_object_or_404(Negocio, id=negocio_id)
    negocio.destacado = not negocio.destacado
    negocio.save()
    return JsonResponse({"destacado": negocio.destacado, "message": "Estado destacado de negocio actualizado."})