from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from logistica.models import PerfilRepartidor
from .models import Usuario

def obtener_sedes_usuario(user):
    from catalogo.models import Sede
    if getattr(user, 'rol', None) == 'negocio':
        if hasattr(user, 'negocio'):
            return Sede.objects.filter(negocio=user.negocio)
        else:
            return Sede.objects.filter(usuarios_asignados__usuario=user)
    return Sede.objects.none()

def registro_view(request):
    if request.method == "POST":
        usuario = request.POST.get("username")
        correo = request.POST.get("email")
        contrasena = request.POST.get("password")
        rol_seleccionado = request.POST.get("rol")

        if Usuario.objects.filter(username__iexact=usuario).exists():
            messages.error(request, "Ese nombre de usuario ya está en uso. Elige otro.")
            return redirect("registro")

        nuevo_usuario = Usuario.objects.create_user(
            username=usuario,
            email=correo,
            password=contrasena,
            rol=rol_seleccionado,
        )

        if rol_seleccionado == "repartidor":
            PerfilRepartidor.objects.get_or_create(
                usuario=nuevo_usuario,
                defaults={"estado_actual": PerfilRepartidor.EstadoActual.INACTIVO},
            )

        messages.success(request, "Cuenta creada con éxito. Ahora puedes iniciar sesión.")
        return redirect("login")

    return render(request, "usuarios/registro.html")

def home_view(request):
    return render(request, "home.html")

def login_view(request):
    if request.method == "POST":
        usuario = request.POST.get("username")
        contrasena = request.POST.get("password")

        user = authenticate(request, username=usuario, password=contrasena)

        if user is not None:
            login(request, user)
            messages.success(request, f"Bienvenido de vuelta, {user.username}.")

            if user.es_repartidor:
                perfil, _ = PerfilRepartidor.objects.get_or_create(
                    usuario=user,
                    defaults={"estado_actual": PerfilRepartidor.EstadoActual.INACTIVO},
                )
                perfil.estado_actual = PerfilRepartidor.EstadoActual.DISPONIBLE
                perfil.save(update_fields=["estado_actual"])
                return redirect("logistica:mi_pedido_activo")

            elif user.es_negocio:
                from catalogo.models import Negocio
                sedes = obtener_sedes_usuario(user)
                if not Negocio.objects.filter(propietario=user).exists() and not sedes.exists():
                    messages.info(request, "Registra los datos de tu establecimiento para empezar.")
                    return redirect("registrar_negocio")
                
                if sedes.count() == 1:
                    request.session['sede_id'] = sedes.first().id
                    return redirect("pedidos:panel_negocio")
                elif sedes.count() > 1:
                    return redirect("seleccionar_sede")
                
                return redirect("pedidos:panel_negocio")

            elif user.es_admin:
                return redirect("dashboard_inicio")

            elif user.es_cliente:
                return redirect("home_negocios")

            return redirect("home")

        messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, "usuarios/login.html")

@login_required
def seleccionar_sede_view(request):
    sedes = obtener_sedes_usuario(request.user)
    
    if request.method == "POST":
        sede_id = request.POST.get('sede_id')
        if sedes.filter(id=sede_id).exists():
            request.session['sede_id'] = int(sede_id)
            messages.success(request, "Sede seleccionada correctamente.")
            return redirect("pedidos:panel_negocio")
        else:
            messages.error(request, "Sede no válida.")
            
    return render(request, "usuarios/seleccionar_sede.html", {"sedes": sedes})

@login_required
def perfil_view(request):
    if request.method == "POST":
        request.user.email = request.POST.get("email")
        request.user.telefono = request.POST.get("telefono")
        request.user.direccion = request.POST.get("direccion")
        request.user.save()
        messages.success(request, "Perfil actualizado correctamente.")
        return redirect("perfil")

    return render(request, "usuarios/perfil.html")

def logout_view(request):
    logout(request)
    messages.info(request, "Has cerrado sesión exitosamente.")
    return redirect('login')


from django.http import JsonResponse
from django.views.decorators.http import require_POST
import json

@login_required
@require_POST
def actualizar_perfil_cliente_api(request):
    try:
        data = json.loads(request.body)
    except Exception:
        return JsonResponse({"detail": "Datos JSON no válidos."}, status=400)

    first_name = data.get("first_name", "").strip()
    last_name = data.get("last_name", "").strip()
    telefono = data.get("telefono", "").strip()
    direccion = data.get("direccion", "").strip()
    latitud_str = data.get("latitud")
    longitud_str = data.get("longitud")

    if not (first_name and last_name and telefono and direccion and latitud_str and longitud_str):
        return JsonResponse({"detail": "Todos los campos (nombre, apellido, teléfono, dirección y ubicación en el mapa) son obligatorios."}, status=400)

    try:
        from decimal import Decimal
        latitud = Decimal(str(latitud_str))
        longitud = Decimal(str(longitud_str))
    except Exception:
        return JsonResponse({"detail": "Coordenadas no válidas."}, status=400)

    user = request.user
    user.first_name = first_name
    user.last_name = last_name
    user.telefono = telefono
    user.direccion = direccion
    user.latitud = latitud
    user.longitud = longitud
    user.save()

    return JsonResponse({"message": "Perfil completado con éxito."})
