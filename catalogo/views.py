from rest_framework import viewsets
from .models import Categoria, Negocio, Producto
from .serializers import CategoriaSerializer, NegocioSerializer, ProductoSerializer
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from .permissions import IsPropietarioOrReadOnly, IsAdminOrReadOnly
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from .forms import NegocioForm, ProductoForm, SedeForm
from .models import Sede





class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer
    permission_classes = [IsAdminOrReadOnly]

class NegocioViewSet(viewsets.ModelViewSet):
    queryset = Negocio.objects.all()
    serializer_class = NegocioSerializer
    permission_classes = [IsAuthenticated, IsPropietarioOrReadOnly]

class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['categoria', 'sede', 'disponible']
    search_fields = ['nombre', 'descripcion']
    permission_classes = [IsAuthenticatedOrReadOnly, IsPropietarioOrReadOnly]

def catalogo_vista(request):
    return home_negocios(request)
    
def registrar_negocio(request):
    negocio = Negocio.objects.filter(propietario=request.user).first()
    
    if not negocio:
        from usuarios.models import UsuarioSede
        if UsuarioSede.objects.filter(usuario=request.user).exists():
            return redirect('editar_mi_sede')
            
    sede = Sede.objects.filter(negocio=negocio).first() if negocio else None
    
    if request.method == 'POST':
        form = NegocioForm(request.POST, request.FILES, instance=negocio)
        form_sede = SedeForm(request.POST, instance=sede)
        if form.is_valid() and form_sede.is_valid():
            obj = form.save(commit=False)
            if not negocio:
                obj.propietario = request.user
            obj.save()
            
            obj_s = form_sede.save(commit=False)
            obj_s.negocio = obj
            obj_s.save()
            
            request.session['sede_id'] = obj_s.id
            return redirect('pedidos:panel_negocio')
    else:
        form = NegocioForm(instance=negocio)
        form_sede = SedeForm(instance=sede)
        
    return render(request, 'catalogo/form_negocio.html', {
        'form': form,
        'form_sede': form_sede,
        'existe': negocio is not None
    })

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden

# 2. Panel de administración CRUD de productos
@login_required(login_url='login')
def administrar_productos(request):
    es_usuario_admin = request.user.is_superuser or getattr(request.user, 'rol', None) == 'admin'
    es_usuario_negocio = getattr(request.user, 'rol', None) == 'negocio'
    
    if not (es_usuario_admin or es_usuario_negocio):
        return HttpResponseForbidden("No tienes permiso para acceder a esta página.")
        
    if es_usuario_admin:
        productos = Producto.objects.all()
    else:
        sede_id = request.session.get('sede_id')
        productos = Producto.objects.filter(sede_id=sede_id)
        
    return render(request, 'catalogo/admin_productos.html', {'productos': productos})

# 3. Crear o editar producto (Para el CRUD)
@login_required(login_url='login')
def guardar_producto(request, id=0):
    es_usuario_admin = request.user.is_superuser or getattr(request.user, 'rol', None) == 'admin'
    es_usuario_negocio = getattr(request.user, 'rol', None) == 'negocio'
    
    if not (es_usuario_admin or es_usuario_negocio):
        return HttpResponseForbidden("No tienes permiso para realizar esta acción.")

    sede_actual = None
    if es_usuario_negocio:
        sede_id = request.session.get('sede_id')
        if not sede_id:
            return redirect('registrar_negocio')
        sede_actual = get_object_or_404(Sede, id=sede_id)

    if id == 0:
        producto = None
        form = ProductoForm(request.POST or None, request.FILES or None, user=request.user)
    else:
        if es_usuario_admin:
            producto = get_object_or_404(Producto, pk=id)
        else:
            producto = get_object_or_404(Producto, pk=id, sede=sede_actual)
        form = ProductoForm(request.POST or None, request.FILES or None, instance=producto, user=request.user)
        
    if request.method == "POST":
        if form.is_valid():
            obj = form.save(commit=False)
            if es_usuario_negocio:
                obj.sede = sede_actual
            obj.save()
            if obj.stock < 3:
                from django.contrib import messages
                messages.warning(request, f"¡Alerta! El producto '{obj.nombre}' ha quedado con stock bajo ({obj.stock} unidades).")
            return redirect('administrar_productos')
            
    return render(request, 'catalogo/form_producto.html', {'form': form, 'id': id})

# 4. Eliminar producto (Para el CRUD)
@login_required(login_url='login')
def eliminar_producto(request, id):
    es_usuario_admin = request.user.is_superuser or getattr(request.user, 'rol', None) == 'admin'
    es_usuario_negocio = getattr(request.user, 'rol', None) == 'negocio'
    
    if not (es_usuario_admin or es_usuario_negocio):
        return HttpResponseForbidden("No tienes permiso para realizar esta acción.")

    if es_usuario_admin:
        producto = get_object_or_404(Producto, pk=id)
    else:
        sede_id = request.session.get('sede_id')
        producto = get_object_or_404(Producto, pk=id, sede_id=sede_id)
        
    producto.delete()
    return redirect('administrar_productos')

# 5. Activar/Desactivar disponibilidad con un solo clic
@login_required(login_url='login')
def cambiar_disponibilidad(request, id):
    es_usuario_admin = request.user.is_superuser or getattr(request.user, 'rol', None) == 'admin'
    es_usuario_negocio = getattr(request.user, 'rol', None) == 'negocio'
    
    if not (es_usuario_admin or es_usuario_negocio):
        return HttpResponseForbidden("No tienes permiso para realizar esta acción.")

    if es_usuario_admin:
        producto = get_object_or_404(Producto, pk=id)
    else:
        sede_id = request.session.get('sede_id')
        producto = get_object_or_404(Producto, pk=id, sede_id=sede_id)
        
    producto.disponible = not producto.disponible
    producto.save()
    return redirect('administrar_productos')


# 1. VISTA HOME / LANDING: Listado de negocios con buscador y filtros
def home_negocios(request):
    if request.user.is_authenticated:
        rol = getattr(request.user, 'rol', None)
        if rol == 'negocio':
            return redirect('pedidos:panel_negocio')
        elif rol == 'repartidor':
            return redirect('logistica:mi_pedido_activo')
        elif rol == 'admin' or request.user.is_superuser:
            return redirect('dashboard_inicio')

    from django.db.models import Avg, Value
    from django.db.models.functions import Coalesce

    sedes = Sede.objects.filter(estado=True, negocio__isnull=False)
    
    buscar_query = request.GET.get('q', '')
    rubro_filtro = request.GET.get('rubro', '')
    filtro_abierto = request.GET.get('abierto', '')
    filtro_destacado = request.GET.get('destacado', '')
    ordenar_filtro = request.GET.get('ordenar', '')
    
    if buscar_query:
        from django.db.models import Q
        sedes = sedes.filter(
            Q(negocio__nombre_comercial__icontains=buscar_query) |
            Q(negocio__rubro__icontains=buscar_query) |
            Q(negocio__descripcion__icontains=buscar_query) |
            Q(productos__nombre__icontains=buscar_query, productos__disponible=True, productos__stock__gt=0) |
            Q(productos__descripcion__icontains=buscar_query, productos__disponible=True, productos__stock__gt=0)
        ).distinct()
        
    if rubro_filtro:
        sedes = sedes.filter(negocio__rubro=rubro_filtro)

    if filtro_abierto == '1':
        sedes = sedes.filter(abierto=True)

    if filtro_destacado == '1':
        sedes = sedes.filter(negocio__destacado=True)

    # Anotar con el promedio de puntuación de valoraciones
    sedes = sedes.annotate(
        promedio_rating=Coalesce(Avg('valoraciones__puntuacion'), Value(5.0))
    )

    if ordenar_filtro == 'calificacion':
        sedes = sedes.order_by('-promedio_rating')

    # 1. Recomendaciones: Las mejor valoradas
    sedes_mejor_valoradas = Sede.objects.filter(estado=True, valoraciones__isnull=False).distinct()
    if rubro_filtro:
        sedes_mejor_valoradas = sedes_mejor_valoradas.filter(negocio__rubro=rubro_filtro)
    sedes_mejor_valoradas = sedes_mejor_valoradas.annotate(
        promedio_rating=Avg('valoraciones__puntuacion')
    ).order_by('-promedio_rating')[:5]

    # 2. Recomendaciones de últimos pedidos hechos
    from pedidos.models import Pedido
    ultimas_sedes_pedidas = []
    if request.user.is_authenticated:
        sedes_ids = []
        pedidos_recientes = Pedido.objects.filter(cliente=request.user).order_by('-fecha_creacion')
        for p in pedidos_recientes:
            if p.sede_id not in sedes_ids:
                sedes_ids.append(p.sede_id)
            if len(sedes_ids) >= 5:
                break
        
        ultimas_sedes = Sede.objects.filter(id__in=sedes_ids, estado=True)
        if rubro_filtro:
            ultimas_sedes = ultimas_sedes.filter(negocio__rubro=rubro_filtro)
        
        ultimas_sedes_pedidas = ultimas_sedes.annotate(
            promedio_rating=Coalesce(Avg('valoraciones__puntuacion'), Value(5.0))
        )

    # 3. Productos en oferta
    productos_oferta = Producto.objects.filter(
        disponible=True, 
        stock__gt=0, 
        descuento_porcentaje__gt=0,
        sede__estado=True
    )
    if rubro_filtro:
        productos_oferta = productos_oferta.filter(sede__negocio__rubro=rubro_filtro)
    productos_oferta = productos_oferta.select_related('sede__negocio')[:6]
        
    return render(request, 'catalogo/home.html', {
        'sedes': sedes,
        'buscar_query': buscar_query,
        'rubro_filtro': rubro_filtro,
        'filtro_abierto': filtro_abierto == '1',
        'filtro_destacado': filtro_destacado == '1',
        'ordenar_filtro': ordenar_filtro,
        'sedes_mejor_valoradas': sedes_mejor_valoradas,
        'ultimas_sedes_pedidas': ultimas_sedes_pedidas,
        'productos_oferta': productos_oferta,
    })

# 2. VISTA DETALLE SEDE: Muestra una sede y su catálogo de productos específico
@login_required(login_url='login')
def detalle_sede(request, sede_id):
    rol = getattr(request.user, 'rol', None)
    if rol == 'negocio':
        return redirect('pedidos:panel_negocio')
    elif rol == 'repartidor':
        return redirect('logistica:mi_pedido_activo')
    elif rol == 'admin' or request.user.is_superuser:
        return redirect('dashboard_inicio')

    sede = get_object_or_404(Sede, pk=sede_id, estado=True)
    # Filtramos para que solo muestre los productos de esta sede, que estén disponibles y tengan stock
    productos = Producto.objects.filter(sede=sede, disponible=True, stock__gt=0)
    
    # Obtener el estado actual del carrito
    from pedidos.views import _build_carrito_context
    carrito_ctx = _build_carrito_context(request)
    
    return render(request, 'catalogo/detalle_sede.html', {
        'sede': sede,
        'productos': productos,
        'items_carrito': carrito_ctx['items_carrito'],
        'total_carrito': carrito_ctx['total_carrito'],
        'costo_envio': carrito_ctx['costo_envio'],
        'total_con_envio': carrito_ctx['total_con_envio']
    })

# --- GESTION DE SEDES ---

@login_required(login_url='login')
def gestionar_sedes(request):
    es_propietario = getattr(request.user, 'rol', None) == 'negocio'
    if not es_propietario:
        return HttpResponseForbidden("Solo el propietario puede gestionar las sedes.")
    
    negocio = Negocio.objects.filter(propietario=request.user).first()
    if not negocio:
        return redirect('registrar_negocio')
        
    sedes = Sede.objects.filter(negocio=negocio)
    return render(request, 'catalogo/gestionar_sedes.html', {'sedes': sedes, 'negocio': negocio})

@login_required(login_url='login')
def crear_sede(request, sede_id=None):
    es_propietario = getattr(request.user, 'rol', None) == 'negocio'
    if not es_propietario:
        return HttpResponseForbidden("Solo el propietario puede gestionar las sedes.")
        
    negocio = Negocio.objects.filter(propietario=request.user).first()
    if not negocio:
        return redirect('registrar_negocio')
        
    if sede_id:
        sede = get_object_or_404(Sede, id=sede_id, negocio=negocio)
    else:
        sede = None
        
    if request.method == 'POST':
        form = SedeForm(request.POST, instance=sede)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.negocio = negocio
            obj.save()
            from django.contrib import messages
            messages.success(request, f"Sede '{obj.nombre}' guardada con éxito.")
            return redirect('gestionar_sedes')
    else:
        form = SedeForm(instance=sede)
        
    return render(request, 'catalogo/form_sede_solo.html', {'form': form, 'sede_id': sede_id})

@login_required(login_url='login')
def activar_desactivar_sede(request, sede_id):
    es_propietario = getattr(request.user, 'rol', None) == 'negocio'
    if not es_propietario:
        return HttpResponseForbidden("Solo el propietario puede gestionar las sedes.")
        
    negocio = Negocio.objects.filter(propietario=request.user).first()
    sede = get_object_or_404(Sede, id=sede_id, negocio=negocio)
    sede.estado = not sede.estado
    sede.save()
    messages.success(request, f"Estado de sede '{sede.nombre}' actualizado.")
    return redirect('gestionar_sedes')

@login_required(login_url='login')
def editar_mi_sede(request):
    sede_id = request.session.get('sede_id')
    if not sede_id:
        return redirect('pedidos:panel_negocio')
        
    sede = get_object_or_404(Sede, id=sede_id)
    
    from usuarios.models import UsuarioSede
    es_propietario = (sede.negocio.propietario == request.user)
    es_admin_sede = UsuarioSede.objects.filter(usuario=request.user, sede=sede, rol='admin_sede').exists()
    
    if not (es_propietario or es_admin_sede):
        return HttpResponseForbidden("No tienes permiso para editar los detalles de esta sede.")
        
    if request.method == 'POST':
        form = SedeForm(request.POST, instance=sede)
        if form.is_valid():
            form.save()
            from django.contrib import messages
            messages.success(request, f"Datos de la sede '{sede.nombre}' actualizados con éxito.")
            return redirect('pedidos:panel_negocio')
    else:
        form = SedeForm(instance=sede)
        
    return render(request, 'catalogo/form_sede_solo.html', {'form': form, 'sede_id': sede.id})
