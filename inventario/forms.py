from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Persona, OrdenTrabajo, Asignacion, ParteTrabajo, Equipo


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


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Usuario',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Usuario', 'autofocus': True})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña'})
    )


class QuickPersonaForm(forms.ModelForm):
    class Meta:
        model = Persona
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Nombre del usuario'
            }),
        }
        labels = {'nombre': 'Nombre'}


class ParteTrabajoForm(forms.ModelForm):
    personas = forms.ModelMultipleChoiceField(
        queryset=Persona.objects.filter(activo=True),
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'}),
        label='Personas que trabajaron'
    )
    horas_trabajadas = forms.DecimalField(
        label='Horas trabajadas',
        max_digits=6, decimal_places=2, min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.5})
    )
    horas_extras = forms.DecimalField(
        label='Horas extra',
        max_digits=6, decimal_places=2, min_value=0,
        initial=0,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.5})
    )

    class Meta:
        model = ParteTrabajo
        fields = ['acciones', 'cantidad_equipos', 'fecha_inicio', 'fecha_fin']
        widgets = {
            'acciones': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 1, 'max': 10,
                'id': 'id_acciones'
            }),
            'cantidad_equipos': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0,
                'id': 'id_cantidad_equipos'
            }),
            'fecha_inicio': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date',
                'id': 'id_fecha_inicio'
            }),
            'fecha_fin': forms.DateInput(attrs={
                'class': 'form-control', 'type': 'date',
                'id': 'id_fecha_fin'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.persona_inicial = kwargs.pop('persona_inicial', None)
        self.fecha_min = kwargs.pop('fecha_min', None)
        self.fecha_max = kwargs.pop('fecha_max', None)
        super().__init__(*args, **kwargs)
        if self.persona_inicial:
            self.fields['personas'].initial = [self.persona_inicial]
        self.fields['personas'].label_from_instance = lambda obj: f'{obj.apellido} {obj.nombre}'
        if self.fecha_min:
            self.fields['fecha_inicio'].widget.attrs['min'] = self.fecha_min
            self.fields['fecha_fin'].widget.attrs['min'] = self.fecha_min
        if self.fecha_max:
            self.fields['fecha_inicio'].widget.attrs['max'] = self.fecha_max
            self.fields['fecha_fin'].widget.attrs['max'] = self.fecha_max

    def clean_personas(self):
        personas = self.cleaned_data.get('personas')
        if not personas or len(personas) < 1:
            raise forms.ValidationError('Debe seleccionar al menos una persona.')
        return personas

    def clean(self):
        cleaned = super().clean()
        fecha_inicio = cleaned.get('fecha_inicio')
        fecha_fin = cleaned.get('fecha_fin')
        if fecha_inicio and fecha_fin and fecha_fin < fecha_inicio:
            raise forms.ValidationError('La fecha de fin no puede ser anterior a la fecha de inicio.')
        if fecha_inicio and self.fecha_min and fecha_inicio < self.fecha_min:
            raise forms.ValidationError(f'La fecha de inicio no puede ser anterior a {self.fecha_min}.')
        if fecha_fin and self.fecha_max and fecha_fin > self.fecha_max:
            raise forms.ValidationError(f'La fecha de fin no puede ser posterior a {self.fecha_max}.')
        return cleaned


class EquipoForm(forms.ModelForm):
    class Meta:
        model = Equipo
        fields = ['municipio', 'unidad_salud', 'tipo', 'denominacion', 'servicio',
                  'local', 'marca', 'modelo', 'numero_serie', 'estado', 'observaciones', 'frecuencia']
        widgets = {
            'municipio': forms.TextInput(attrs={'class': 'form-control'}),
            'unidad_salud': forms.TextInput(attrs={'class': 'form-control'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'denominacion': forms.TextInput(attrs={'class': 'form-control'}),
            'servicio': forms.TextInput(attrs={'class': 'form-control'}),
            'local': forms.TextInput(attrs={'class': 'form-control'}),
            'marca': forms.TextInput(attrs={'class': 'form-control'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control'}),
            'numero_serie': forms.TextInput(attrs={'class': 'form-control'}),
            'estado': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ej: Funcionando, Afectado, Roto...'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'frecuencia': forms.TextInput(attrs={'class': 'form-control'}),
        }



