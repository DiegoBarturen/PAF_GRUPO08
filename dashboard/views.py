from django.shortcuts import render
from django.contrib.auth.decorators import login_required, user_passes_test
from usuarios.models import Usuario
import csv
from django.http import HttpResponse


# Función de seguridad: Verifica si el usuario tiene rol de admin o es superusuario
def es_admin(user):
    return user.is_authenticated and (user.rol == 'admin' or user.is_superuser)

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='home') # Si no es admin, lo manda al home
def dashboard_inicio(request):
    # Recopilamos estadísticas reales de tu base de datos actual
    total_usuarios = Usuario.objects.count()
    total_clientes = Usuario.objects.filter(rol='cliente').count()
    total_negocios = Usuario.objects.filter(rol='negocio').count()
    total_repartidores = Usuario.objects.filter(rol='repartidor').count()

    context = {
        'total_usuarios': total_usuarios,
        'total_clientes': total_clientes,
        'total_negocios': total_negocios,
        'total_repartidores': total_repartidores,
        # Aquí luego tu compañero agregará total_pedidos, ingresos, etc.
    }
    
    return render(request, 'dashboard/inicio.html', context)

@login_required(login_url='login')
@user_passes_test(es_admin, login_url='home')
def exportar_reporte_usuarios(request):
    # 1. Crear la respuesta HTTP configurada para descargar un archivo
    response = HttpResponse(content_type='text/csv')
    # El nombre del archivo que se descargará
    response['Content-Disposition'] = 'attachment; filename="reporte_usuarios_nativo.csv"'

    # 2. Crear el "escritor" de CSV
    writer = csv.writer(response)

    # 3. Escribir la primera fila (Los encabezados de las columnas)
    writer.writerow(['ID', 'Nombre', 'Correo', 'Rol', 'Fecha de Registro'])

    # 4. Traer todos los usuarios de la base de datos y escribirlos fila por fila
    usuarios = Usuario.objects.all().order_by('-date_joined') # Ordenados por el más reciente
    
    for usuario in usuarios:
        writer.writerow([
            usuario.id,
            f"{usuario.first_name} {usuario.last_name}",
            usuario.email,
            usuario.rol.upper(), # Ponemos el rol en mayúsculas para que se vea mejor
            usuario.date_joined.strftime('%Y-%m-%d %H:%M') # Formato de fecha limpio
        ])

    return response
