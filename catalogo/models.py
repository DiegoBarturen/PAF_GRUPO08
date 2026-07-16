from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from core.models import ModeloBase
from usuarios.models import Usuario

RUBROS = (
    ('restaurante', 'Restaurantes'),
    ('super', 'Súper'),
    ('farmacia', 'Farmacia'),
    ('postres', 'Postres'),
    ('licores', 'Licores'),
    ('mascotas', 'Mascotas'),
)

class Categoria(ModeloBase):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)
    activa = models.BooleanField(default=True)
    rubro = models.CharField(max_length=50, choices=RUBROS, null=True, blank=True, verbose_name="Rubro de Categoría")

    def __str__(self):
        return self.nombre

class Negocio(ModeloBase):
    RUBROS = RUBROS

    propietario = models.OneToOneField(Usuario, on_delete=models.CASCADE, limit_choices_to={'rol': 'negocio'})
    nombre_comercial = models.CharField(max_length=200)
    descripcion = models.TextField()
    destacado = models.BooleanField(default=False)
    rubro = models.CharField(max_length=50, choices=RUBROS, default='restaurante', verbose_name="Rubro de Negocio")
    imagen = models.ImageField(upload_to='negocios/', null=True, blank=True, verbose_name="Imagen de Portada")
    logo = models.ImageField(upload_to='logos/', null=True, blank=True, verbose_name="Logo del Local")

    @property
    def logo_url(self):
        if self.logo and hasattr(self.logo, 'url'):
            return self.logo.url
        return f"https://ui-avatars.com/api/?name={self.nombre_comercial}&background=random&color=fff&size=100"

    @property
    def imagen_url(self):
        if self.imagen and hasattr(self.imagen, 'url'):
            return self.imagen.url
        if self.rubro == 'restaurante':
            return 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=600&q=80'
        elif self.rubro == 'super':
            return 'https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=600&q=80'
        elif self.rubro == 'farmacia':
            return 'https://images.unsplash.com/photo-1586015555751-63bb77f4322a?auto=format&fit=crop&w=600&q=80'
        elif self.rubro == 'postres':
            return 'https://images.unsplash.com/photo-1587314168485-3236d6710814?auto=format&fit=crop&w=600&q=80'
        elif self.rubro == 'licores':
            return 'https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?auto=format&fit=crop&w=600&q=80'
        elif self.rubro == 'mascotas':
            return 'https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?auto=format&fit=crop&w=600&q=80'
        return 'https://images.unsplash.com/photo-1555396273-367ea4eb4db5?auto=format&fit=crop&w=600&q=80'

    @property
    def valoracion_promedio(self):
        # La valoración se calcula sobre todas las sedes del negocio
        valoraciones = Valoracion.objects.filter(sede__negocio=self)
        if valoraciones.exists():
            promedio = sum(v.puntuacion for v in valoraciones) / valoraciones.count()
            return round(promedio, 1)
        return 5.0

    @property
    def abierto(self):
        return self.sedes.filter(abierto=True).exists()

    @property
    def costo_envio(self):
        sede = self.sedes.first()
        return sede.costo_envio if sede else 0.00

    def __str__(self):
        return self.nombre_comercial

class Sede(ModeloBase):
    negocio = models.ForeignKey(Negocio, on_delete=models.CASCADE, related_name='sedes')
    nombre = models.CharField(max_length=150, verbose_name="Nombre de la Sede", default="Sede Principal")
    direccion = models.CharField(max_length=255)
    telefono = models.CharField(max_length=15)
    abierto = models.BooleanField(default=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitud = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    hora_apertura = models.TimeField(null=True, blank=True)
    hora_cierre = models.TimeField(null=True, blank=True)
    costo_envio = models.DecimalField(max_digits=6, decimal_places=2, default=0.00, verbose_name="Costo de Envío")
    estado = models.BooleanField(default=True, verbose_name="Sede Activa")

    @property
    def logo_url(self):
        return self.negocio.logo_url

    @property
    def imagen_url(self):
        return self.negocio.imagen_url

    @property
    def nombre_comercial(self):
        return self.negocio.nombre_comercial

    @property
    def rubro(self):
        return self.negocio.rubro

    def get_rubro_display(self):
        return self.negocio.get_rubro_display()

    @property
    def valoracion_promedio(self):
        valoraciones = self.valoraciones.all()
        if valoraciones.exists():
            promedio = sum(v.puntuacion for v in valoraciones) / valoraciones.count()
            return round(promedio, 1)
        return 5.0

    def __str__(self):
        return f"{self.negocio.nombre_comercial} - {self.nombre}"


class Producto(ModeloBase):
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='productos')
    categoria = models.ForeignKey(Categoria, on_delete=models.SET_NULL, null=True, related_name='productos')
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField()
    precio = models.DecimalField(max_digits=8, decimal_places=2)
    descuento_porcentaje = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(100)])
    precio_oferta = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    disponible = models.BooleanField(default=True)
    imagen = models.ImageField(upload_to='productos/', null=True, blank=True)
    stock = models.IntegerField(default=0)

    def save(self, *args, **kwargs):
        if self.descuento_porcentaje and self.descuento_porcentaje > 0:
            from decimal import Decimal
            descuento = (self.precio * Decimal(self.descuento_porcentaje)) / Decimal(100)
            self.precio_oferta = (self.precio - descuento).quantize(Decimal('0.01'))
        else:
            self.precio_oferta = None
        super().save(*args, **kwargs)
    
    @property
    def imagen_url(self):
        if self.imagen and hasattr(self.imagen, 'url'):
            return self.imagen.url
        return '/static/images/default_product.png'

    @property
    def stock_options(self):
        limit = min(10, self.stock)
        return range(1, limit + 1)

    def __str__(self):
        return f"{self.nombre} - {self.sede.nombre}"


class Valoracion(ModeloBase):
    sede = models.ForeignKey(Sede, on_delete=models.CASCADE, related_name='valoraciones')
    cliente = models.ForeignKey(Usuario, on_delete=models.CASCADE)
    puntuacion = models.IntegerField(default=5)  # 1 a 5 estrellas
    comentario = models.TextField(blank=True, null=True)
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Valoración"
        verbose_name_plural = "Valoraciones"
        ordering = ["-fecha"]
        unique_together = [('sede', 'cliente')]  # Un cliente solo puede valorar 1 vez por sede

    def __str__(self):
        return f"{self.cliente.username} - {self.puntuacion}* en {self.sede.nombre}"