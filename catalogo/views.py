from rest_framework import viewsets
from .models import Categoria, Negocio, Producto
from .serializers import CategoriaSerializer, NegocioSerializer, ProductoSerializer
from rest_framework.filters import SearchFilter
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.permissions import IsAuthenticated
from .permissions import IsPropietarioOrReadOnly 
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from django.shortcuts import render, redirect, get_object_or_404 # <-- CORREGIDO AQUÍ (404)
from .forms import NegocioForm, ProductoForm





class CategoriaViewSet(viewsets.ModelViewSet):
    queryset = Categoria.objects.all()
    serializer_class = CategoriaSerializer

class NegocioViewSet(viewsets.ModelViewSet):
    queryset = Negocio.objects.all()
    serializer_class = NegocioSerializer
    permission_classes = [IsAuthenticated, IsPropietarioOrReadOnly]

class ProductoViewSet(viewsets.ModelViewSet):
    queryset = Producto.objects.all()
    serializer_class = ProductoSerializer
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_fields = ['categoria', 'negocio', 'disponible']
    search_fields = ['nombre', 'descripcion']
    permission_classes = [IsAuthenticatedOrReadOnly, IsPropietarioOrReadOnly]

def catalogo_vista(request):
    # Usamos select_related('negocio') para que traiga el nombre del negocio en la misma consulta
    productos_lista = Producto.objects.filter(disponible=True).select_related('negocio')
    return render(request, 'catalogo/vitrina.html', {'productos': productos_lista})
    
def registrar_negocio(request):
    negocio = Negocio.objects.filter(propietario=request.user).first()
    
    if request.method == 'POST':
        form = NegocioForm(request.POST, instance=negocio)
        if form.is_valid():
            obj = form.save(commit=False)
            if not negocio:
                obj.propietario = request.user
            obj.save()
            return redirect('pedidos:panel_negocio')
    else:
        form = NegocioForm(instance=negocio)
        
    return render(request, 'catalogo/form_negocio.html', {
        'form': form,
        'existe': negocio is not None
    })

# 2. Panel de administración CRUD de productos
def administrar_productos(request):
    productos = Producto.objects.all()
    return render(request, 'catalogo/admin_productos.html', {'productos': productos})

# 3. Crear o editar producto (Para el CRUD)
def guardar_producto(request, id=0):
    if request.method == "POST":
        if id == 0:
            form = ProductoForm(request.POST, request.FILES)
        else:
            producto = get_object_or_404(Producto, pk=id) # <-- CORREGIDO AQUÍ
            form = ProductoForm(request.POST, request.FILES, instance=producto)
        
        if form.is_valid():
            form.save()
            return redirect('administrar_productos')
    else:
        if id == 0:
            form = ProductoForm()
        else:
            producto = get_object_or_404(Producto, pk=id) # <-- CORREGIDO AQUÍ
            form = ProductoForm(instance=producto)
    return render(request, 'catalogo/form_producto.html', {'form': form})

# 4. Eliminar producto (Para el CRUD)
def eliminar_producto(request, id):
    producto = get_object_or_404(Producto, pk=id) # <-- CORREGIDO AQUÍ
    producto.delete()
    return redirect('administrar_productos')

# 5. Activar/Desactivar disponibilidad con un solo clic
def cambiar_disponibilidad(request, id):
    producto = get_object_or_404(Producto, pk=id) # <-- CORREGIDO AQUÍ
    producto.disponible = not producto.disponible
    producto.save()
    return redirect('administrar_productos')


# 1. VISTA HOME / LANDING: Listado de negocios con buscador y filtros
def home_negocios(request):
    negocios = Negocio.objects.all()
    
    buscar_query = request.GET.get('q', '')
    # Comentamos temporalmente el filtro por categoría hasta que agregues el campo al modelo
    # categoria_filtro = request.GET.get('categoria', '')
    
    if buscar_query:
        # CORREGIDO: Cambiamos 'nombre' por 'nombre_comercial' que es tu campo real
        negocios = negocios.filter(nombre_comercial__icontains=buscar_query)
        
    return render(request, 'catalogo/home.html', {
        'negocios': negocios,
        'buscar_query': buscar_query,
        # 'categoria_filtro': categoria_filtro
    })

# 2. VISTA DETALLE NEGOCIO: Muestra un negocio y su catálogo de productos específico
def detalle_negocio(request, negocio_id):
    negocio = get_object_or_404(Negocio, pk=negocio_id)
    # Filtramos para que solo muestre los productos de este negocio Y que estén disponibles
    productos = Producto.objects.filter(negocio=negocio, disponible=True)
    
    return render(request, 'catalogo/detalle_negocio.html', {
        'negocio': negocio,
        'productos': productos
    })
