from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from logistica.models import PerfilRepartidor
from .models import Usuario

def registro_view(request):
    if request.method == "POST":
        usuario = request.POST.get("username")
        correo = request.POST.get("email")
        contrasena = request.POST.get("password")
        rol_seleccionado = request.POST.get("rol")

        if Usuario.objects.filter(username=usuario).exists():
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

            # REDIRECCIÓN AUTOMÁTICA SEGÚN EL ROL REAL
            if user.es_repartidor:
                perfil, _ = PerfilRepartidor.objects.get_or_create(
                    usuario=user,
                    defaults={"estado_actual": PerfilRepartidor.EstadoActual.INACTIVO},
                )
                perfil.estado_actual = PerfilRepartidor.EstadoActual.DISPONIBLE
                perfil.save(update_fields=["estado_actual"])
                return redirect("logistica:mi_pedido_activo")

            elif user.es_negocio:
                # Envía al restaurante directo a su panel de órdenes entrantes
                return redirect("pedidos:panel_negocio")

            elif user.es_admin:
                # Envía al administrador al panel estadístico global
                return redirect("dashboard_inicio")

            elif user.es_cliente:
                # Envía al cliente directo a la Landing de negocios para que empiece a comprar
                return redirect("home_negocios")

            return redirect("home")

        messages.error(request, "Usuario o contraseña incorrectos.")

    return render(request, "usuarios/login.html")

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
    # Redirigimos al usuario a la pantalla de login tras cerrar sesión
    return redirect('login')
