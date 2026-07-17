from django import forms
from .models import Persona, OrdenTrabajo, Asignacion


class PersonaForm(forms.ModelForm):
    class Meta:
        model = Persona
        fields = ['nombre', 'apellido', 'email', 'telefono', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'correo@ejemplo.com'}),
            'telefono': forms.TextInput(attrs={'class': 'form-control', 'placeholder': '+52 555 555 5555'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class OrdenTrabajoForm(forms.ModelForm):
    class Meta:
        model = OrdenTrabajo
        fields = ['numero_orden', 'descripcion', 'fecha', 'completada']
        widgets = {
            'numero_orden': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ej: 2024-001'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción de la orden...'
            }),
            'fecha': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date'
            }),
            'completada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class AsignacionForm(forms.ModelForm):
    class Meta:
        model = Asignacion
        fields = ['persona', 'fecha', 'acciones', 'horas_diurnas', 'horas_extras']
        widgets = {
            'persona': forms.Select(attrs={'class': 'form-select'}),
            'fecha': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'acciones': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
            'horas_diurnas': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.5}),
            'horas_extras': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.5}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['persona'].queryset = Persona.objects.filter(activo=True)
        self.fields['persona'].label_from_instance = lambda obj: f'{obj.nombre} {obj.apellido}'
