from django.db import models

class EstadoPedido(models.TextChoices):
    """
    Definición de estados para la máquina de estados estricta 
    de la aplicación de Pedidos.
    """
    RECIBIDO = "RE", "Recibido"
    CONFIRMADO = "CO", "Confirmado"
    EN_PREPARACION = "PR", "En preparación"
    LISTO_RECOJO = "LI", "Listo para recojo"
    EN_CAMINO = "CA", "En camino"
    ENTREGADO = "EN", "Entregado"
    CANCELADO = "CN", "Cancelado"
    