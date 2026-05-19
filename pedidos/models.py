# pedidos/models.py
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from config.choices import EstadoPedido
from pedidos.validators import validar_cantidad_positiva


class Pedido(models.Model):
    """
    Modelo principal del pedido.
    Representa una orden realizada por un cliente con cálculos automáticos.
    """
    METODO_PAGO_EFECTIVO = "efectivo"
    METODO_PAGO_POS = "pos"
    METODOS_PAGO = (
        (METODO_PAGO_EFECTIVO, _("Efectivo contra entrega")),
        (METODO_PAGO_POS, _("Tarjeta con POS contra entrega")),
    )

    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pedidos_realizados",
        verbose_name=_("Cliente")
    )
    negocio = models.ForeignKey(
        'catalogo.Negocio',  # Configurado como String para evitar importaciones circulares
        on_delete=models.PROTECT,
        related_name="pedidos_negocio",
        verbose_name=_("Negocio")
    )
    repartidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pedidos_asignados",
        verbose_name=_("Repartidor"),
        null=True,
        blank=True
    )
    estado = models.CharField(
        max_length=2,
        choices=EstadoPedido.choices,
        default=EstadoPedido.RECIBIDO,
        verbose_name=_("Estado del pedido")
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Subtotal")
    )
    costo_envio = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Costo de envío")
    )
    total = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Total")
    )
    direccion_entrega = models.TextField(
        verbose_name=_("Dirección de entrega")
    )
    telefono = models.CharField(
        max_length=15,
        blank=True,
        default="",
        verbose_name=_("Teléfono de contacto")
    )
    metodo_pago = models.CharField(
        max_length=20,
        choices=METODOS_PAGO,
        default=METODO_PAGO_EFECTIVO,
        verbose_name=_("Método de pago")
    )
    observaciones = models.TextField(
        null=True,
        blank=True,
        verbose_name=_("Observaciones")
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Fecha de creación")
    )
    fecha_actualizacion = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Fecha de actualización")
    )

    class Meta:
        db_table = "pedidos"
        ordering = ["-fecha_creacion"]
        verbose_name = _("Pedido")
        verbose_name_plural = _("Pedidos")

    def __str__(self):
        return f"Pedido #{self.pk} - {self.cliente} ({self.get_estado_display()})"

    def clean(self):
        super().clean()
        errors = {}

        # 1. VALIDAR HORARIO DEL NEGOCIO
        if self.negocio_id:
            negocio = self.negocio
            if hasattr(negocio, "abierto") and not negocio.abierto:
                errors["negocio"] = _("El negocio actualmente se encuentra cerrado.")

        # 2. VALIDACIÓN DE CONSISTENCIA DE ESTADO (Rescatado del código 2)
        if self.estado == EstadoPedido.EN_CAMINO and not self.repartidor:
            errors['repartidor'] = _("No se puede cambiar el estado a 'En camino' sin asignar un repartidor.")

        # 3. VALIDAR STOCK DE PRODUCTOS (Solo si el pedido ya existe en la BD)
        if self.pk:
            items = self.items_pedido.select_related("producto").all()
            for item in items:
                if item.cantidad > item.producto.stock:
                    errors["stock"] = f"Stock insuficiente para el producto {item.producto.nombre}."

        if errors:
            raise ValidationError(errors)

    def calcular_totales(self):
        """Recalcula subtotal y total del pedido basados en sus ítems."""
        subtotal_calculado = sum(item.subtotal for item in self.items_pedido.all())
        self.subtotal = subtotal_calculado
        self.total = subtotal_calculado + self.costo_envio

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class ItemPedido(models.Model):
    """
    Representa cada producto agregado al pedido (Detalle del carrito).
    """
    pedido = models.ForeignKey(
        Pedido,
        on_delete=models.CASCADE,
        related_name="items_pedido",
        verbose_name=_("Pedido")
    )
    producto = models.ForeignKey(
        'catalogo.Producto',  # Configurado como String para evitar importaciones circulares
        on_delete=models.PROTECT,
        related_name="items_en_pedidos",
        verbose_name=_("Producto")
    )
    cantidad = models.PositiveIntegerField(
        validators=[validar_cantidad_positiva],
        verbose_name=_("Cantidad")
    )
    precio_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,       # Permite que pase la validación inicial del formulario vacía
        blank=True,      # Permite que se renderice vacío en formularios si fuera necesario
        verbose_name=_("Precio unitario (Histórico)")
    )
    subtotal = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        editable=False,
        verbose_name=_("Subtotal")
    )
    fecha_creacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Fecha de creación")
    )

    class Meta:
        db_table = "items_pedido"
        ordering = ["id"]
        verbose_name = _("Item de pedido")
        verbose_name_plural = _("Items de pedido")
        unique_together = ('pedido', 'producto')  # Rescatado del código 2: Evita duplicados directos

    def __str__(self):
        return f"{self.producto} x {self.cantidad}"

    def clean(self):
        super().clean()
        errors = {}

        # VALIDAR DISPONIBILIDAD Y STOCK DEL PRODUCTO
        if hasattr(self, 'producto') and self.producto:
            if hasattr(self.producto, "disponible") and not self.producto.disponible:
                errors["producto"] = _("El producto no se encuentra disponible.")
            
            stock_disponible = getattr(self.producto, 'stock', None)
            if stock_disponible is not None and self.cantidad > stock_disponible:
                errors["cantidad"] = f"Stock insuficiente para {self.producto.nombre}. Stock actual: {stock_disponible}."

        if errors:
            raise ValidationError(errors)

    @transaction.atomic
    def save(self, *args, **kwargs):
        self.full_clean()

        # Rescatado del código 1: Congela el precio actual del catálogo para el histórico
        if hasattr(self.producto, 'precio'):
            self.precio_unitario = self.producto.precio

        # Calcular el subtotal de esta línea
        self.subtotal = self.precio_unitario * self.cantidad

        super().save(*args, **kwargs)

        # Recalcular totales del pedido padre y guardarlo de forma segura
        self.pedido.calcular_totales()
        Pedido.objects.filter(pk=self.pedido.pk).update(
            subtotal=self.pedido.subtotal,
            total=self.pedido.total
        )
