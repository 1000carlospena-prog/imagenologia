from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import Departamento, Persona, OrdenTrabajo, Asignacion, ParteTrabajo, Equipo


class LoginDepartamentoForm(forms.Form):
    departamento = forms.ModelChoiceField(
        label='Departamento',
        queryset=Departamento.objects.filter(activo=True).order_by('nombre'),
        widget=forms.Select(attrs={
            'class': 'form-select', 'autocomplete': 'off',
        }),
        empty_label='Selecciona un departamento',
    )
    contrasena = forms.CharField(
        label='Contraseña del departamento',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Contraseña',
            'autocomplete': 'current-password',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        departamento = cleaned.get('departamento')
        contrasena = cleaned.get('contrasena')
        if departamento and contrasena:
            if not departamento.verificar_contrasena(contrasena):
                self.add_error('contrasena', 'Contraseña incorrecta para este departamento.')
            elif not departamento.activo:
                self.add_error('departamento', 'Este departamento está desactivado.')
        return cleaned


class CrearDepartamentoForm(forms.Form):
    nombre = forms.CharField(
        label='Nombre del departamento',
        max_length=120,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 'placeholder': 'Ej: Cardiología', 'autocomplete': 'off',
        }),
    )
    contrasena = forms.CharField(
        label='Contraseña',
        min_length=4,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Mínimo 4 caracteres',
            'autocomplete': 'new-password',
        }),
    )
    confirmacion = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Repite la contraseña',
            'autocomplete': 'new-password',
        }),
    )

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre'].strip()
        if Departamento.objects.filter(nombre__iexact=nombre).exists():
            raise forms.ValidationError('Ya existe un departamento con ese nombre.')
        return nombre

    def clean(self):
        cleaned = super().clean()
        contrasena = cleaned.get('contrasena')
        confirmacion = cleaned.get('confirmacion')
        if contrasena and confirmacion and contrasena != confirmacion:
            self.add_error('confirmacion', 'Las contraseñas no coinciden.')
        return cleaned


class DepartamentoEditarForm(forms.ModelForm):
    class Meta:
        model = Departamento
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 'autocomplete': 'off',
            }),
        }


class DepartamentoContrasenaForm(forms.Form):
    contrasena = forms.CharField(
        label='Nueva contraseña',
        min_length=4,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Mínimo 4 caracteres',
            'autocomplete': 'new-password',
        }),
    )
    confirmacion = forms.CharField(
        label='Confirmar contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Repite la contraseña',
            'autocomplete': 'new-password',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        contrasena = cleaned.get('contrasena')
        confirmacion = cleaned.get('confirmacion')
        if contrasena and confirmacion and contrasena != confirmacion:
            self.add_error('confirmacion', 'Las contraseñas no coinciden.')
        return cleaned


class _DepartamentoMixin:
    def __init__(self, *args, **kwargs):
        self.departamento_actual = kwargs.pop('departamento', None)
        self.departamentos_qs = kwargs.pop('departamentos', None)
        super().__init__(*args, **kwargs)
        self._configurar_departamento()

    def _es_global(self):
        return self.departamento_actual is None or not self.departamento_actual.restringido

    def _configurar_departamento(self):
        field = self.fields['departamento']
        if self._es_global():
            field.queryset = self.departamentos_qs or Departamento.objects.all()
        else:
            field.queryset = Departamento.objects.filter(pk=self.departamento_actual.pk)
            field.initial = self.departamento_actual
            field.disabled = True

    def save(self, commit=True):
        instance = super().save(commit=False)
        if not self._es_global():
            instance.departamento = self.departamento_actual
        if commit:
            instance.save()
        return instance


class PersonaForm(_DepartamentoMixin, forms.ModelForm):
    class Meta:
        model = Persona
        fields = ['nombre', 'apellido', 'departamento', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre', 'autocomplete': 'given-name'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido', 'autocomplete': 'family-name'}),
            'departamento': forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class OrdenTrabajoForm(_DepartamentoMixin, forms.ModelForm):
    class Meta:
        model = OrdenTrabajo
        fields = ['numero_orden', 'descripcion', 'fecha', 'completada', 'departamento']
        widgets = {
            'numero_orden': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Ej: 2024-001', 'autocomplete': 'off'
            }),
            'descripcion': forms.Textarea(attrs={
                'class': 'form-control', 'rows': 3, 'placeholder': 'Descripción de la orden...', 'autocomplete': 'off'
            }),
            'fecha': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': 'form-control', 'type': 'date', 'autocomplete': 'off'}
            ),
            'completada': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'departamento': forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
        }


class AsignacionForm(forms.ModelForm):
    class Meta:
        model = Asignacion
        fields = ['persona', 'fecha', 'acciones', 'horas_diurnas', 'horas_extras']
        widgets = {
            'persona': forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
            'fecha': forms.DateInput(format='%Y-%m-%d', attrs={'class': 'form-control', 'type': 'date', 'autocomplete': 'off'}),
            'acciones': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'autocomplete': 'off'}),
            'horas_diurnas': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.5, 'autocomplete': 'off'}),
            'horas_extras': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'step': 0.5, 'autocomplete': 'off'}),
        }

    def __init__(self, *args, **kwargs):
        personas_qs = kwargs.pop('personas_qs', None)
        super().__init__(*args, **kwargs)
        self.fields['persona'].queryset = personas_qs or Persona.objects.filter(activo=True)
        self.fields['persona'].label_from_instance = lambda obj: f'{obj.nombre} {obj.apellido}'


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        label='Usuario',
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Usuario', 'autofocus': True, 'autocomplete': 'username'})
    )
    password = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Contraseña', 'autocomplete': 'current-password'})
    )


class QuickPersonaForm(forms.ModelForm):
    class Meta:
        model = Persona
        fields = ['nombre']
        widgets = {
            'nombre': forms.TextInput(attrs={
                'class': 'form-control', 'placeholder': 'Nombre del usuario', 'autocomplete': 'off'
            }),
        }
        labels = {'nombre': 'Nombre'}


class ParteTrabajoForm(_DepartamentoMixin, forms.ModelForm):
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
        fields = ['acciones', 'cantidad_equipos', 'fecha_inicio', 'fecha_fin', 'departamento']
        widgets = {
            'acciones': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 1, 'max': 10,
                'id': 'id_acciones'
            }),
            'cantidad_equipos': forms.NumberInput(attrs={
                'class': 'form-control', 'min': 0,
                'id': 'id_cantidad_equipos'
            }),
            'fecha_inicio': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': 'form-control', 'type': 'date', 'id': 'id_fecha_inicio'}
            ),
            'fecha_fin': forms.DateInput(
                format='%Y-%m-%d',
                attrs={'class': 'form-control', 'type': 'date', 'id': 'id_fecha_fin'}
            ),
            'departamento': forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
        }

    def __init__(self, *args, **kwargs):
        personas_qs = kwargs.pop('personas_qs', None)
        self.persona_inicial = kwargs.pop('persona_inicial', None)
        self.fecha_min = kwargs.pop('fecha_min', None)
        self.fecha_max = kwargs.pop('fecha_max', None)
        super().__init__(*args, **kwargs)
        if personas_qs is not None:
            self.fields['personas'].queryset = personas_qs
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


class EquipoForm(_DepartamentoMixin, forms.ModelForm):
    class Meta:
        model = Equipo
        fields = ['municipio', 'unidad_salud', 'tipo', 'denominacion', 'servicio',
                  'local', 'marca', 'modelo', 'numero_serie', 'estado', 'observaciones',
                  'frecuencia', 'ubicacion_temporal_municipio', 'ubicacion_temporal_unidad',
                  'nota_interna', 'departamento']
        widgets = {
            'municipio': forms.TextInput(attrs={'class': 'form-control', 'list': 'municipio-sugerencias', 'autocomplete': 'off'}),
            'unidad_salud': forms.TextInput(attrs={'class': 'form-control', 'list': 'unidad-sugerencias', 'autocomplete': 'off'}),
            'tipo': forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
            'denominacion': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'servicio': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'local': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'marca': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'modelo': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'numero_serie': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'estado': forms.TextInput(attrs={'class': 'form-control', 'list': 'estado-sugerencias', 'autocomplete': 'off'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'autocomplete': 'off'}),
            'frecuencia': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'ubicacion_temporal_municipio': forms.TextInput(attrs={'class': 'form-control', 'list': 'municipio-temporal-sugerencias', 'autocomplete': 'off'}),
            'ubicacion_temporal_unidad': forms.TextInput(attrs={'class': 'form-control', 'list': 'unidad-temporal-sugerencias', 'autocomplete': 'off'}),
            'nota_interna': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'autocomplete': 'off'}),
            'departamento': forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
        }