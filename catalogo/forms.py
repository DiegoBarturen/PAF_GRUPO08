from django import forms
from .models import Negocio, Producto

class NegocioForm(forms.ModelForm):
    class Meta:
        model = Negocio
        fields = '__all__'  # <-- Django mapea automáticamente tus campos reales

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Le aplicamos las clases de Bootstrap dinámicamente a los campos que encuentre
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = '__all__'  # <-- Django mapea automáticamente tus campos reales

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            # Si es el checkbox de disponibilidad, usa la clase check de Bootstrap
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})
                