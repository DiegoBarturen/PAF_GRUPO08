from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib import messages
from .models import Usuario

def login_view(request):
    # Si el usuario hace clic en "Iniciar Sesión" (envía el formulario)
    if request.method == 'POST':
        usuario = request.POST.get('username')
        contrasena = request.POST.get('password')
        
        # Django verifica si el usuario y contraseña coinciden en la base de datos
        user = authenticate(request, username=usuario, password=contrasena)
        
        if user is not None:
            login(request, user)
            messages.success(request, f'¡Bienvenido de vuelta, {user.username}!')
            
            # Temporalmente lo enviamos al panel admin. 
            # Luego tus compañeros cambiarán esto según el rol (ej. redirect al catálogo o dashboard)
            return redirect('home')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
            
    # Si solo está visitando la página, le mostramos el HTML
    return render(request, 'usuarios/login.html')

def registro_view(request):
    if request.method == 'POST':
        usuario = request.POST.get('username')
        correo = request.POST.get('email')
        contrasena = request.POST.get('password')
        rol_seleccionado = request.POST.get('rol')
        
        # Validación 1: Verificar que el nombre de usuario no exista ya
        if Usuario.objects.filter(username=usuario).exists():
            messages.error(request, 'Ese nombre de usuario ya está en uso. Elige otro.')
            return redirect('registro')
            
        # Creamos el usuario en la base de datos con el rol que eligió
        nuevo_usuario = Usuario.objects.create_user(
            username=usuario,
            email=correo,
            password=contrasena,
            rol=rol_seleccionado
        )
        
        messages.success(request, '¡Cuenta creada con éxito! Ahora puedes iniciar sesión.')
        return redirect('login')
        
    return render(request, 'usuarios/registro.html')

def home_view(request):
    return render(request, 'home.html')
