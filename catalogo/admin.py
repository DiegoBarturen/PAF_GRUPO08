from django.contrib import admin
from .models import Categoria, Negocio, Sede, Producto, Valoracion

admin.site.register(Categoria)
admin.site.register(Negocio)
admin.site.register(Sede)
admin.site.register(Producto)
admin.site.register(Valoracion)
