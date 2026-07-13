from rest_framework import serializers
from .models import Categoria, Negocio, Producto

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = '__all__' # Trae todos los campos automáticamente [cite: 100]

class NegocioSerializer(serializers.ModelSerializer):
    class Meta:
        model = Negocio
        fields = '__all__'

# Serializador con datos anidados para que el Frontend lea el nombre fácil [cite: 113, 115]
class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.CharField(source='categoria.nombre', read_only=True)
    negocio_nombre = serializers.CharField(source='negocio.nombre_comercial', read_only=True)

    class Meta:
        model = Producto
        fields = [
            'id', 'nombre', 'descripcion', 'precio', 'disponible', 
            'categoria', 'categoria_nombre', 'negocio', 'negocio_nombre', 'imagen', 'imagen_url'
        ]