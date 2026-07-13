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
    METODO_PAGO_QR = "qr"
    METODO_PAGO_TARJETA = "tarjeta"
    METODOS_PAGO = (
        (METODO_PAGO_EFECTIVO, _("Efectivo contra entrega")),
        (METODO_PAGO_POS, _("Tarjeta con POS contra entrega")),
        (METODO_PAGO_QR, _("Pago con Código QR (En línea)")),
        (METODO_PAGO_TARJETA, _("Pago con Tarjeta (En línea)")),
    )

    cliente = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pedidos_realizados",
        verbose_name=_("Cliente")
    )
    sede = models.ForeignKey(
        'catalogo.Sede',  # Configurado como String para evitar importaciones circulares
        on_delete=models.PROTECT,
        related_name="pedidos_sede",
        verbose_name=_("Sede")
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
    descuento = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Descuento")
    )
    cupon = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name=_("Cupón")
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
    latitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Latitud")
    )
    longitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Longitud")
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

        # 1. VALIDAR HORARIO DE LA SEDE
        if self.sede_id:
            sede = self.sede
            if hasattr(sede, "abierto") and not sede.abierto:
                errors["sede"] = _("La sede actualmente se encuentra cerrada.")

        # 2. VALIDACIÓN DE CONSISTENCIA DE ESTADO (Rescatado del código 2)
        if self.estado == EstadoPedido.EN_CAMINO and not self.repartidor:
            errors['repartidor'] = _("No se puede cambiar el estado a 'En camino' sin asignar un repartidor.")

        # 3. VALIDAR STOCK DE PRODUCTOS (Solo si el pedido ya existe en la BD)
        if self.pk:
            items = self.items_pedido.select_related("producto").all()
            for item in items:
                if item.cantidad > item.producto.stock:
                    errors["stock"] = f"Stock insuficiente para el producto {item.producto.nombre}."

        # 4. MÁQUINA DE ESTADOS ESTRICTA
        if self.pk:
            try:
                original = Pedido.objects.get(pk=self.pk)
                if original.estado != self.estado:
                    # 1. Verificar si el estado original es terminal
                    if original.estado in [EstadoPedido.ENTREGADO, EstadoPedido.CANCELADO]:
                        errors['estado'] = _(
                            f"No se pueden realizar cambios sobre un pedido en estado final ({original.get_estado_display()})."
                        )
                    # 2. Si el nuevo estado es Cancelado
                    elif self.estado == EstadoPedido.CANCELADO:
                        if original.estado in [EstadoPedido.EN_CAMINO, EstadoPedido.ENTREGADO]:
                            errors['estado'] = _(
                                f"No se puede cancelar el pedido cuando está en estado: {original.get_estado_display()}."
                            )
                    # 3. Transiciones progresivas entre estados activos
                    else:
                        state_order = {
                            EstadoPedido.RECIBIDO: 1,
                            EstadoPedido.CONFIRMADO: 2,
                            EstadoPedido.EN_PREPARACION: 3,
                            EstadoPedido.LISTO_RECOJO: 4,
                            EstadoPedido.EN_CAMINO: 5,
                            EstadoPedido.ENTREGADO: 6,
                        }
                        
                        idx_orig = state_order.get(original.estado)
                        idx_new = state_order.get(self.estado)
                        
                        if idx_orig is None or idx_new is None or idx_new <= idx_orig:
                            errors['estado'] = _(
                                f"Transición de estado inválida: no se permite cambiar de {original.get_estado_display()} a {self.get_estado_display()}."
                            )
            except Pedido.DoesNotExist:
                pass

        if errors:
            raise ValidationError(errors)

    def calcular_totales(self):
        """Recalcula subtotal, descuento y total del pedido basados en sus ítems."""
        subtotal_calculado = sum(item.subtotal for item in self.items_pedido.all())
        self.subtotal = subtotal_calculado
        self.total = subtotal_calculado - self.descuento + self.costo_envio

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

        # Rescatado del código 1: Congela el precio actual del catálogo para el histórico (prioriza oferta)
        if hasattr(self.producto, 'precio_oferta') and self.producto.precio_oferta is not None and self.producto.precio_oferta > 0:
            self.precio_unitario = self.producto.precio_oferta
        elif hasattr(self.producto, 'precio'):
            self.precio_unitario = self.producto.precio

        # Calcular el subtotal de esta línea
        self.subtotal = self.precio_unitario * self.cantidad

        super().save(*args, **kwargs)

        # Recalcular totales del pedido padre y guardarlo de forma segura
        self.pedido.calcular_totales()
        Pedido.objects.filter(pk=self.pedido.pk).update(
            subtotal=self.pedido.subtotal,
            descuento=self.pedido.descuento,
            total=self.pedido.total
        )
