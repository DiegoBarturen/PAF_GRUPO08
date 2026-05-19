# pedidos/validators.py
from django.core.exceptions import ValidationError

def validar_cantidad_positiva(value):
    """
    Valida que la cantidad de productos en un ítem de pedido 
    sea estrictamente mayor a cero.
    """
    if value <= 0:
        raise ValidationError(
            "La cantidad ingresada debe ser un número entero mayor a cero.",
            params={"value": value},
        )