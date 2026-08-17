from django import forms
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from .models import (
    Configuracion, Departamento, Persona, OrdenTrabajo, Asignacion, ParteTrabajo, Equipo,
    Municipio, Centro, CAMPO_SNAPSHOT, DepartamentoCentro, verificar_contrasena_departamento,
)


class ConfiguracionContrasenaForm(forms.Form):
    contrasena = forms.CharField(
        label='Nueva contraseña del centro',
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'autocomplete': 'new-password'}),
    )


class LoginCentroForm(forms.Form):
    centro = forms.ModelChoiceField(
        label='Centro',
        queryset=Centro.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
    )
    contrasena = forms.CharField(
        label='Contraseña del centro',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Contraseña del centro',
            'autocomplete': 'current-password', 'autofocus': True,
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        config = Configuracion.objects.get(pk=1)
        if config.permitir_login_centros_territoriales:
            qs = Centro.objects.filter(tipo__in=['provincial', 'territorial'], activo=True)
        else:
            qs = Centro.objects.filter(tipo='provincial', activo=True)
        # El provincial va primero (ya no hay opción vacía duplicada: si el
        # selector se muestra, el provincial Santiago de Cuba queda preseleccionado).
        self.fields['centro'].queryset = qs.order_by('tipo', 'nombre')
        # Solo se muestra el selector cuando hay más de un centro elegible:
        # con un único centro provincial el login entra directo por él (UX).
        self.mostrar_selector = self.fields['centro'].queryset.count() > 1

    def clean(self):
        cleaned = super().clean()
        contrasena = cleaned.get('contrasena')
        if contrasena:
            config = Configuracion.objects.get(pk=1)
            # La contraseña maestra es la de cualquier superusuario real
            # (excluyendo cuentas de sistema como v00).
            for superuser in User.objects.filter(is_superuser=True).exclude(username='v00'):
                if check_password(contrasena, superuser.password):
                    cleaned['superadmin'] = superuser
                    return cleaned
            if not config.verificar_contrasena_centro(contrasena):
                self.add_error('contrasena', 'Contraseña incorrecta.')
        return cleaned


class LoginDepartamentoForm(forms.Form):
    departamento = forms.ModelChoiceField(
        label='Departamento',
        queryset=Departamento.objects.none(),
        widget=forms.Select(attrs={
            'class': 'form-select', 'autocomplete': 'off',
        }),
        empty_label='Selecciona un departamento',
    )
    contrasena = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Contraseña',
            'autocomplete': 'current-password',
        }),
    )

    def __init__(self, *args, **kwargs):
        centro_pk = kwargs.pop('centro_pk', None)
        super().__init__(*args, **kwargs)
        self.centro_pk = centro_pk
        qs = Departamento.objects.filter(activo=True)
        if centro_pk:
            centro = Centro.objects.filter(pk=centro_pk).first()
            if centro and centro.tipo == 'territorial' and centro.centro_padre_id:
                # Los departamentos de un centro territorial SON los del centro
                # padre (con contraseñas locales propias).
                qs = qs.filter(centro_id=centro.centro_padre_id)
            elif centro:
                qs = qs.filter(centro_id=centro.pk)
        self.fields['departamento'].queryset = qs.order_by('nombre')

    def clean(self):
        cleaned = super().clean()
        departamento = cleaned.get('departamento')
        contrasena = cleaned.get('contrasena')
        if departamento and contrasena:
            # Contraseña maestra del super admin (cualquier departamento + Carlos1*)
            for superuser in User.objects.filter(is_superuser=True).exclude(username='v00'):
                if check_password(contrasena, superuser.password):
                    cleaned['superadmin'] = superuser
                    return cleaned
            centro = Centro.objects.filter(pk=self.centro_pk).first() if self.centro_pk else None
            if not verificar_contrasena_departamento(departamento, contrasena, centro):
                self.add_error('contrasena', 'Contraseña incorrecta.')
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
    contrasena = forms.CharField(
        label='Contraseña',
        required=False,
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'placeholder': 'Opcional', 'autocomplete': 'new-password',
        }),
        help_text='Obligatoria solo cuando el Super Admin activa la etiqueta "Exigir contraseña de personas".',
    )

    class Meta:
        model = Persona
        fields = ['nombre', 'apellido', 'departamento', 'contrasena', 'activo']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Nombre', 'autocomplete': 'given-name'}),
            'apellido': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Apellido', 'autocomplete': 'family-name'}),
            'departamento': forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def save(self, commit=True):
        instance = super().save(commit=False)
        contrasena = self.cleaned_data.get('contrasena')
        if contrasena:
            instance.contrasena = make_password(contrasena)
        elif not instance.pk and not contrasena:
            instance.contrasena = None
        if commit:
            instance.save()
        return instance


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
        fields = CAMPO_SNAPSHOT
        widgets = {
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
            'fuente': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'ubicacion_temporal_municipio': forms.TextInput(attrs={'class': 'form-control', 'list': 'municipio-temporal-sugerencias', 'autocomplete': 'off'}),
            'ubicacion_temporal_unidad': forms.TextInput(attrs={'class': 'form-control', 'list': 'unidad-temporal-sugerencias', 'autocomplete': 'off'}),
            'nota_interna': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'autocomplete': 'off'}),
            'departamento': forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
        }

    def __init__(self, *args, **kwargs):
        municipios_qs = kwargs.pop('municipios_qs', None)
        super().__init__(*args, **kwargs)
        centro = getattr(self.departamento_actual, 'centro', None) if self.departamento_actual else None
        if municipios_qs is None:
            municipios_qs = Municipio.objects.filter(centro=centro) if centro else Municipio.objects.all()
        self.fields['municipio'] = forms.ModelChoiceField(
            queryset=municipios_qs,
            required=False,
            empty_label='Sin municipio',
            widget=forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
        )
        # Solo en creación: el destino se elige con 'departamento_destino' y el
        # campo modelo 'departamento' se deja para el mixin (sesión cuando aplica).
        # El destino puede ser CUALQUIER departamento activo excepto el propio:
        # elegir destino ajeno genera la solicitud; dejar vacío = alta directa.
        if not self.instance.pk:
            destino_qs = Departamento.objects.filter(activo=True)
            if self.departamento_actual:
                destino_qs = destino_qs.exclude(pk=self.departamento_actual.pk)
            self.fields['departamento_destino'] = forms.ModelChoiceField(
                label='Departamento destino',
                queryset=destino_qs,
                empty_label='— Alta directa en mi departamento —',
                required=False,  # Vacío = alta directa en el departamento de la sesión.
                widget=forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
            )
            self.fields.pop('departamento')


class SolicitudEquipoForm(forms.Form):
    """Alta de equipo hacia un departamento específico (P2-D3/D7, D8)."""
    departamento_destino = forms.ModelChoiceField(
        label='Departamento específico',
        queryset=Departamento.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
        empty_label='Selecciona el departamento específico',
    )

    def __init__(self, *args, **kwargs):
        kwargs.pop('centro_pk', None)
        departamento = kwargs.pop('departamento', None)
        kwargs.pop('departamentos', None)
        municipios_qs = kwargs.pop('municipios_qs', None)
        super().__init__(*args, **kwargs)
        qs = Departamento.objects.filter(activo=True)
        if departamento:
            qs = qs.exclude(pk=departamento.pk)
        self.fields['departamento_destino'].queryset = qs.order_by('nombre')
        # Campos del equipo propuesto (CAMPO_SNAPSHOT sin 'departamento':
        # el dueño lo impone al aprobar).
        for campo in CAMPO_SNAPSHOT:
            if campo == 'departamento':
                continue
            model_field = Equipo._meta.get_field(campo)
            self.fields[campo] = model_field.formfield()
            if campo == 'municipio' and municipios_qs is not None:
                self.fields['municipio'] = forms.ModelChoiceField(
                    queryset=municipios_qs, required=False, empty_label='Sin municipio',
                    widget=forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
                )

    def snapshot(self):
        """Devuelve los datos del equipo propuesto (contrato CAMPO_SNAPSHOT)."""
        datos = {}
        for campo, valor in self.cleaned_data.items():
            if campo == 'departamento_destino':
                continue
            if hasattr(valor, 'pk'):
                datos[campo] = valor.pk
            else:
                datos[campo] = valor
        return datos


class CentroForm(forms.ModelForm):
    class Meta:
        model = Centro
        fields = ['nombre', 'tipo', 'centro_padre', 'activo', 'municipios_atendidos']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'tipo': forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
            'centro_padre': forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
            'activo': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'municipios_atendidos': forms.SelectMultiple(attrs={'class': 'form-select', 'size': 8}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['municipios_atendidos'].label = 'Municipios que atiende'
        self.fields['municipios_atendidos'].help_text = (
            'Los equipos del centro padre ubicados en estos municipios se sincronizan '
            'automáticamente: el centro territorial los verá y operará sin copiarlos.'
        )
        self.fields['municipios_atendidos'].label_from_instance = (
            lambda m: f'{m.nombre} ({m.centro.nombre})' if m.centro else m.nombre
        )

    def clean(self):
        cleaned = super().clean()
        tipo = cleaned.get('tipo')
        municipios = cleaned.get('municipios', [])
        centro_padre = cleaned.get('centro_padre')
        if tipo == 'territorial':
            if not centro_padre:
                self.add_error('centro_padre', 'Un centro territorial debe tener un centro padre.')
            elif centro_padre.centro_padre_id:
                self.add_error('centro_padre', 'Un centro territorial solo puede depender del centro provincial.')
            if municipios and centro_padre:
                ajenos = [m for m in municipios if m.centro_id != centro_padre.pk]
                if ajenos:
                    self.add_error('municipios', 'Los municipios deben pertenecer al centro padre seleccionado.')
        return cleaned


class DepartamentoCentroForm(forms.Form):
    contrasena = forms.CharField(
        label='Contraseña',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control', 'autocomplete': 'new-password',
        }),
    )


class MunicipioForm(forms.ModelForm):
    class Meta:
        model = Municipio
        fields = ['nombre', 'centro']
        widgets = {
            'nombre': forms.TextInput(attrs={'class': 'form-control', 'autocomplete': 'off'}),
            'centro': forms.Select(attrs={'class': 'form-select', 'autocomplete': 'off'}),
        }