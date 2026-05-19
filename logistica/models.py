from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class PerfilRepartidor(models.Model):
    class EstadoActual(models.TextChoices):
        DISPONIBLE = "disponible", _("Disponible")
        EN_RUTA = "en_ruta", _("En ruta")
        INACTIVO = "inactivo", _("Inactivo")

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil_repartidor",
        verbose_name=_("Usuario"),
    )
    estado_actual = models.CharField(
        max_length=20,
        choices=EstadoActual.choices,
        default=EstadoActual.DISPONIBLE,
        verbose_name=_("Estado actual"),
    )
    vehiculo = models.CharField(
        max_length=100,
        blank=True,
        verbose_name=_("Vehiculo"),
    )
    latitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Latitud"),
    )
    longitud = models.DecimalField(
        max_digits=9,
        decimal_places=6,
        null=True,
        blank=True,
        verbose_name=_("Longitud"),
    )
    ultima_actualizacion_ubicacion = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Ultima actualizacion de ubicacion"),
    )

    class Meta:
        verbose_name = _("Perfil de repartidor")
        verbose_name_plural = _("Perfiles de repartidor")
        ordering = ["usuario__username"]

    def __str__(self):
        return f"{self.usuario.username} - {self.get_estado_actual_display()}"

    def clean(self):
        super().clean()
        if self.usuario and getattr(self.usuario, "rol", None) != "repartidor":
            raise ValidationError(
                {"usuario": _("Solo se puede crear un perfil para usuarios con rol repartidor.")}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class AsignacionPedido(models.Model):
    pedido = models.OneToOneField(
        "pedidos.Pedido",
        on_delete=models.CASCADE,
        related_name="asignacion_logistica",
        verbose_name=_("Pedido"),
    )
    repartidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="asignaciones_logistica",
        verbose_name=_("Repartidor"),
    )
    activa = models.BooleanField(
        default=True,
        verbose_name=_("Asignacion activa"),
    )
    asignado_en = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Asignado en"),
    )
    recogido_en = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Recogido en"),
    )
    entregado_en = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name=_("Entregado en"),
    )

    class Meta:
        verbose_name = _("Asignacion de pedido")
        verbose_name_plural = _("Asignaciones de pedidos")
        ordering = ["-asignado_en"]
        constraints = [
            models.UniqueConstraint(
                fields=["repartidor"],
                condition=models.Q(activa=True),
                name="unique_active_assignment_per_driver",
            )
        ]

    def __str__(self):
        return f"Pedido #{self.pedido_id} -> {self.repartidor.username}"

    def clean(self):
        super().clean()
        errors = {}

        if self.repartidor and getattr(self.repartidor, "rol", None) != "repartidor":
            errors["repartidor"] = _("El usuario asignado debe tener rol repartidor.")

        if self.recogido_en and self.recogido_en < self.asignado_en:
            errors["recogido_en"] = _("La fecha de recojo no puede ser anterior a la asignacion.")

        if self.entregado_en:
            reference_date = self.recogido_en or self.asignado_en
            if reference_date and self.entregado_en < reference_date:
                errors["entregado_en"] = _("La fecha de entrega no puede ser anterior al recojo o asignacion.")

        if not self.activa and not self.entregado_en:
            errors["activa"] = _("Una asignacion solo debe cerrarse cuando la entrega haya finalizado.")

        if errors:
            raise ValidationError(errors)

    def marcar_recogido(self):
        self.recogido_en = timezone.now()
        self.save(update_fields=["recogido_en"])

    def marcar_entregado(self):
        self.entregado_en = timezone.now()
        self.activa = False
        self.save(update_fields=["entregado_en", "activa"])

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


class HistorialEntrega(models.Model):
    class EventoEntrega(models.TextChoices):
        ASIGNADO = "asignado", _("Asignado")
        RECOGIDO = "recogido", _("Recogido")
        ENTREGADO = "entregado", _("Entregado")

    pedido = models.ForeignKey(
        "pedidos.Pedido",
        on_delete=models.CASCADE,
        related_name="historial_logistico",
        verbose_name=_("Pedido"),
    )
    repartidor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="historial_entregas",
        verbose_name=_("Repartidor"),
    )
    evento = models.CharField(
        max_length=20,
        choices=EventoEntrega.choices,
        verbose_name=_("Evento"),
    )
    observacion = models.TextField(
        blank=True,
        verbose_name=_("Observacion"),
    )
    fecha = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("Fecha"),
    )

    class Meta:
        verbose_name = _("Historial de entrega")
        verbose_name_plural = _("Historiales de entrega")
        ordering = ["-fecha"]

    def __str__(self):
        return f"Pedido #{self.pedido_id} - {self.get_evento_display()}"

    def clean(self):
        super().clean()
        if self.repartidor and getattr(self.repartidor, "rol", None) != "repartidor":
            raise ValidationError(
                {"repartidor": _("El historial solo puede registrarse para usuarios con rol repartidor.")}
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
