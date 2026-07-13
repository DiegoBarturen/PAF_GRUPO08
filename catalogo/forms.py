from django import forms
from .models import Negocio, Producto, Sede

class NegocioForm(forms.ModelForm):
    class Meta:
        model = Negocio
        exclude = ['propietario', 'destacado']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            if 'rubro' in self.fields:
                self.fields['rubro'].disabled = True
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

class SedeForm(forms.ModelForm):
    class Meta:
        model = Sede
        exclude = ['negocio', 'estado']
        widgets = {
            'latitud': forms.TextInput(attrs={'readonly': 'readonly'}),
            'longitud': forms.TextInput(attrs={'readonly': 'readonly'}),
            'hora_apertura': forms.TimeInput(attrs={'type': 'time'}),
            'hora_cierre': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})

class ProductoForm(forms.ModelForm):
    class Meta:
        model = Producto
        fields = '__all__' 

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        es_admin = user and (user.is_superuser or getattr(user, 'rol', None) == 'admin')
        if not es_admin:
            if 'sede' in self.fields:
                del self.fields['sede']
            
            from .models import Negocio, Categoria
            negocio_user = Negocio.objects.filter(propietario=user).first()
            if negocio_user:
                self.fields['categoria'].queryset = Categoria.objects.filter(rubro=negocio_user.rubro, activa=True)
                
        for name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.update({'class': 'form-check-input'})
            else:
                field.widget.attrs.update({'class': 'form-control'})