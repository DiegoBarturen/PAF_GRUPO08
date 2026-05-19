# pedidos/forms.py
from django import forms 
from pedidos.models import Pedido
from config.choices import EstadoPedido

class CrearPedidoForm(forms.ModelForm):
    """
    Formulario para que el cliente inicie la orden de delivery.
    Incluye los campos que el usuario debe llenar en el frontend,
    siguiendo los estándares de validación de la Sesión 4.
    """
    class Meta:
        model = Pedido
        # Agregamos dirección y observaciones, ya que el cliente debe digitarlas en la web
        fields = ['negocio', 'direccion_entrega', 'observaciones']
        widgets = {
            'direccion_entrega': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 3, 
                'placeholder': 'Ej. Av. Larco 123, Dpto 402'
            }),
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control', 
                'rows': 2, 
                'placeholder': 'Ej. Tocar el timbre fuerte, sin mayonesa, etc.'
            }),
            'negocio': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        """
        Filtramos el queryset para mostrar únicamente los negocios que están abiertos.
        """
        super().__init__(*args, **kwargs)
        if 'negocio' in self.fields:
            self.fields['negocio'].queryset = self.fields['negocio'].queryset.filter(abierto=True)


class ActualizarEstadoPedidoForm(forms.ModelForm):
    """
    Formulario seguro utilizado por el restaurante (Negocio) desde su panel
    para avanzar el pedido en la máquina de estados mediante peticiones POST.
    """
    estado = forms.ChoiceField(
        choices=EstadoPedido.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Pedido
        fields = ['estado']