import math
from django.db import transaction
from django.db.models import Case, IntegerField, Value, When

from config.choices import EstadoPedido
from pedidos.models import Pedido

from .models import AsignacionPedido, HistorialEntrega, PerfilRepartidor


def calcular_distancia_haversine(lat1, lon1, lat2, lon2):
    """
    Calcula la distancia física en kilómetros entre dos coordenadas
    utilizando la fórmula de Haversine.
    """
    if None in (lat1, lon1, lat2, lon2):
        return float('inf')

    # Convertimos a float para evitar errores con tipos Decimal
    lat1, lon1 = float(lat1), float(lon1)
    lat2, lon2 = float(lat2), float(lon2)

    rad = math.pi / 180
    dlat = (lat2 - lat1) * rad
    dlon = (lon2 - lon1) * rad

    a = (math.sin(dlat / 2) ** 2 +
         math.cos(lat1 * rad) * math.cos(lat2 * rad) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return 6371 * c  # Distancia en kilómetros


def _candidatos_disponibles():
    ocupados_ids = AsignacionPedido.objects.filter(activa=True).values_list("repartidor_id", flat=True)

    return (
        PerfilRepartidor.objects.select_related("usuario")
        .filter(
            usuario__rol="repartidor",
            estado_actual=PerfilRepartidor.EstadoActual.DISPONIBLE,
        )
        .exclude(usuario_id__in=ocupados_ids)
        .annotate(
            tiene_ubicacion=Case(
                When(latitud__isnull=False, longitud__isnull=False, then=Value(1)),
                default=Value(0),
                output_field=IntegerField(),
            )
        )
        .order_by("-tiene_ubicacion", "-ultima_actualizacion_ubicacion", "usuario_id")
    )


@transaction.atomic
def asignar_repartidor_a_pedido(pedido):
    """
    Desactivado: Ahora la asignacion es manual por parte del repartidor.
    """
    return None


@transaction.atomic
def asignar_siguiente_pedido_disponible_a_repartidor(repartidor):
    """
    Desactivado: Ahora la asignacion es manual por parte del repartidor.
    """
    return None
