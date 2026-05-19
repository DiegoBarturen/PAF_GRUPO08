from django import forms

from config.choices import EstadoPedido
from pedidos.models import Pedido


class CrearPedidoForm(forms.ModelForm):
    """
    Formulario del checkout web.
    El negocio se asigna automáticamente desde el carrito en la vista.
    """

    class Meta:
        model = Pedido
        fields = ["telefono", "metodo_pago", "direccion_entrega", "observaciones"]
        widgets = {
            "telefono": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "999 999 999",
                }
            ),
            "metodo_pago": forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
            "direccion_entrega": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Ej. Av. Larco 123, Dpto 402",
                }
            ),
            "observaciones": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 2,
                    "placeholder": "Ej. Tocar el timbre fuerte, sin mayonesa, etc.",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        telefono_inicial = kwargs.pop("telefono_inicial", "")
        super().__init__(*args, **kwargs)
        self.fields["telefono"].initial = telefono_inicial
        self.fields["telefono"].required = False
        self.fields["metodo_pago"].required = True


class ActualizarEstadoPedidoForm(forms.ModelForm):
    """
    Formulario seguro utilizado por el restaurante para avanzar el pedido.
    """

    estado = forms.ChoiceField(
        choices=EstadoPedido.choices,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = Pedido
        fields = ["estado"]
