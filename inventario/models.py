import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.hashers import make_password, check_password


class Centro(models.Model):
    """Centro de la jerarquía provincial → territoriales (D4, D8)."""
    TIPO_CHOICES = [
        ('provincial', 'Provincial'),
        ('territorial', 'Territorial'),
    ]
    nombre = models.CharField('Nombre', max_length=100, unique=True)
    tipo = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES, default='provincial')
    centro_padre = models.ForeignKey(
        'self', on_delete=models.PROTECT, null=True, blank=True,
        related_name='hijos', verbose_name='Centro padre',
    )
    activo = models.BooleanField('Activo', default=True)

    class Meta:
        verbose_name = 'Centro'
        verbose_name_plural = 'Centros'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def clean(self):
        if self.tipo == 'territorial' and not self.centro_padre:
            raise ValidationError({
                'centro_padre': 'Un centro territorial debe tener un centro padre.',
            })


def centro_provincial_por_defecto():
    """Centro provincial por defecto ('Santiago de Cuba', D2). Devuelve el pk."""
    centro, _ = Centro.objects.get_or_create(
        nombre='Santiago de Cuba',
        defaults={'tipo': 'provincial'},
    )
    return centro.pk


class Municipio(models.Model):
    """Municipio normalizado vinculado a un centro (D2)."""
    nombre = models.CharField('Nombre', max_length=200)
    centro = models.ForeignKey(
        Centro, on_delete=models.PROTECT,
        related_name='municipios', verbose_name='Centro',
    )

    class Meta:
        verbose_name = 'Municipio'
        verbose_name_plural = 'Municipios'
        ordering = ['nombre']
        unique_together = ['centro', 'nombre']

    def __str__(self):
        return self.nombre


class Departamento(models.Model):
    nombre = models.CharField('Nombre', max_length=120, unique=True)
    contrasena = models.CharField('Contraseña', max_length=255)
    restringido = models.BooleanField('Restringido', default=True)
    activo = models.BooleanField('Activo', default=True)
    creado_en = models.DateTimeField('Creado el', auto_now_add=True)
    centro = models.ForeignKey(
        Centro, on_delete=models.PROTECT, null=True, blank=True,
        related_name='departamentos', verbose_name='Centro',
        default=centro_provincial_por_defecto,
    )

    class Meta:
        verbose_name = 'Departamento'
        verbose_name_plural = 'Departamentos'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre

    def verificar_contrasena(self, contrasena):
        return check_password(contrasena, self.contrasena)


def departamento_por_defecto():
    departamento, _ = Departamento.objects.get_or_create(
        nombre='Imagenología',
        defaults={'contrasena': make_password('imagenologia2026')},
    )
    return departamento.pk


class Configuracion(models.Model):
    """Configuración global del sistema (una sola fila, pk=1)."""
    contrasena_centro = models.CharField('Contraseña del centro', max_length=255)
    exigir_login_centro = models.BooleanField(
        'Exigir login del centro', default=False,
        help_text='Si está activa, hay que entrar primero como centro (CICEM) antes del login de departamento.',
    )
    exigir_contrasena_personas = models.BooleanField(
        'Exigir contraseña de personas', default=False,
        help_text='Si está activa, las personas de los departamentos necesitan contraseña para entrar.',
    )
    permitir_login_centros_territoriales = models.BooleanField(
        'Permitir login de centros territoriales', default=False,
        help_text='Si está activa, el login de centro muestra el selector de centros provinciales y territoriales.',
    )
    mostrar_aprobaciones = models.BooleanField(
        'Mostrar aprobaciones de cambios', default=False,
        help_text='Si está activa, el departamento dueño ve y aprueba las solicitudes y cambios pendientes.',
    )
    mostrar_ordenes_servicio = models.BooleanField(
        'Mostrar órdenes de servicio', default=False,
        help_text='Si está activa, el módulo de órdenes de servicio se muestra en la navegación.',
    )

    class Meta:
        verbose_name = 'Configuración'
        verbose_name_plural = 'Configuración'

    def __str__(self):
        return 'Configuración global'

    def verificar_contrasena_centro(self, contrasena):
        return check_password(contrasena, self.contrasena_centro)


def get_configuracion():
    config, _ = Configuracion.objects.get_or_create(
        pk=1,
        defaults={'contrasena_centro': make_password('12345678')},
    )
    return config


class Persona(models.Model):
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT,
        related_name='personas', verbose_name='Departamento',
        default=departamento_por_defecto,
    )
    nombre = models.CharField('Nombre', max_length=100)
    apellido = models.CharField('Apellido', max_length=100)
    email = models.EmailField('Correo electrónico', blank=True, null=True)
    telefono = models.CharField('Teléfono', max_length=20, blank=True, null=True)
    contrasena = models.CharField('Contraseña', max_length=255, blank=True, null=True)
    activo = models.BooleanField('Activo', default=True)
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)
    fecha_actualizacion = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        verbose_name = 'Persona'
        verbose_name_plural = 'Personas'
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f'{self.nombre} {self.apellido}'


class OrdenTrabajo(models.Model):
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT,
        related_name='ordenes_trabajo', verbose_name='Departamento',
        default=departamento_por_defecto,
    )
    numero_orden = models.CharField('N° de Orden', max_length=50, unique=True)
    descripcion = models.TextField('Descripción', blank=True)
    fecha = models.DateField('Fecha')
    completada = models.BooleanField('Completada', default=False)
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)
    fecha_actualizacion = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        verbose_name = 'Orden de Trabajo'
        verbose_name_plural = 'Órdenes de Trabajo'
        ordering = ['-fecha', '-fecha_creacion']

    def __str__(self):
        return f'OT-{self.numero_orden}'

    def cantidad_personas(self):
        return self.asignaciones.values('persona').distinct().count()


class Asignacion(models.Model):
    orden_trabajo = models.ForeignKey(
        OrdenTrabajo, on_delete=models.CASCADE,
        related_name='asignaciones', verbose_name='Orden de Trabajo'
    )
    persona = models.ForeignKey(
        Persona, on_delete=models.CASCADE,
        related_name='asignaciones', verbose_name='Persona'
    )
    fecha = models.DateField('Fecha')
    acciones = models.PositiveIntegerField(
        'Acciones', default=0,
        validators=[MinValueValidator(0)]
    )
    horas_diurnas = models.DecimalField(
        'Horas diurnas', max_digits=6, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    horas_extras = models.DecimalField(
        'Horas extra', max_digits=6, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'Asignación'
        verbose_name_plural = 'Asignaciones'
        ordering = ['-fecha', 'persona__apellido', 'persona__nombre']
        unique_together = ['orden_trabajo', 'persona', 'fecha']

    def __str__(self):
        return f'{self.persona} - OT-{self.orden_trabajo.numero_orden} - {self.fecha}'

    def total_horas(self):
        return self.horas_diurnas + self.horas_extras


class ParteTrabajo(models.Model):
    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT,
        related_name='partes', verbose_name='Departamento',
        default=departamento_por_defecto,
    )
    fecha_inicio = models.DateField('Fecha de inicio')
    fecha_fin = models.DateField('Fecha de fin')
    acciones = models.PositiveIntegerField(
        'Acciones por equipo', default=1,
        validators=[MinValueValidator(1), MaxValueValidator(10)]
    )
    cantidad_equipos = models.PositiveIntegerField(
        'Cantidad de equipos', default=0,
        validators=[MinValueValidator(0)]
    )
    total_acciones = models.PositiveIntegerField('Total de acciones', default=0)
    creado_por = models.ForeignKey(
        Persona, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='partes_creados', verbose_name='Creado por'
    )
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'Parte de trabajo'
        verbose_name_plural = 'Partes de trabajo'
        ordering = ['-fecha_inicio', '-fecha_creacion']

    def __str__(self):
        return f'Parte {self.pk} ({self.fecha_inicio} - {self.fecha_fin}, {self.total_acciones} acc.)'

    def save(self, *args, **kwargs):
        self.total_acciones = self.acciones * self.cantidad_equipos
        super().save(*args, **kwargs)


class EquipoManager(models.Manager):
    """Manager por defecto de Equipo: excluye equipos eliminados (soft-delete, D5)."""

    def get_queryset(self):
        return super().get_queryset().filter(eliminado_en__isnull=True)


CAMPO_SNAPSHOT = [
    'departamento', 'municipio', 'unidad_salud', 'tipo', 'denominacion', 'servicio',
    'local', 'marca', 'modelo', 'numero_serie', 'estado', 'observaciones', 'frecuencia',
    'fuente', 'ubicacion_temporal_municipio', 'ubicacion_temporal_unidad', 'nota_interna',
]


class Equipo(models.Model):
    TIPO_CHOICES = [
        ('RX', 'Rayos X'),
        ('USD', 'Ultrasonido'),
        ('OTRO', 'Otro'),
    ]

    departamento = models.ForeignKey(
        Departamento, on_delete=models.PROTECT,
        related_name='equipos', verbose_name='Departamento',
        default=departamento_por_defecto,
    )
    municipio = models.ForeignKey(
        'Municipio', on_delete=models.PROTECT, null=True, blank=True,
        related_name='equipos', verbose_name='Municipio',
    )
    unidad_salud = models.CharField('Unidad de salud', max_length=500, blank=True)
    tipo = models.CharField('Tipo', max_length=20, choices=TIPO_CHOICES, default='OTRO')
    denominacion = models.CharField('Denominación', max_length=500, blank=True)
    servicio = models.CharField('Servicio', max_length=300, blank=True)
    local = models.CharField('Local', max_length=300, blank=True)
    marca = models.CharField('Marca', max_length=300, blank=True)
    modelo = models.CharField('Modelo', max_length=300, blank=True)
    numero_serie = models.CharField('N° de Serie', max_length=300, blank=True)
    estado = models.CharField('Estado', max_length=100, blank=True)
    observaciones = models.TextField('Observaciones', blank=True)
    frecuencia = models.CharField('Frecuencia de mantenimiento', max_length=200, blank=True)
    fuente = models.CharField('Archivo fuente', max_length=100, blank=True)
    ubicacion_temporal_municipio = models.CharField('Municipio temporal', max_length=300, blank=True)
    ubicacion_temporal_unidad = models.CharField('Unidad temporal', max_length=500, blank=True)
    nota_interna = models.TextField('Nota interna', blank=True)
    eliminado_en = models.DateTimeField('Eliminado el', null=True, blank=True)
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)

    objects = EquipoManager()
    all_objects = models.Manager()
    class Meta:
        verbose_name = 'Equipo'
        verbose_name_plural = 'Equipos'
        ordering = ['municipio', 'unidad_salud', 'denominacion']

    def __str__(self):
        return f'{self.denominacion or self.tipo} - {self.unidad_salud} ({self.municipio})'


class SolicitudEquipo(models.Model):
    """Solicitud de alta de equipo entre departamentos del mismo centro (D7)."""
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aprobada', 'Aprobada'),
        ('cancelada', 'Cancelada'),
    ]
    equipo = models.ForeignKey(
        Equipo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='solicitudes', verbose_name='Equipo creado',
    )
    datos_equipo = models.JSONField('Datos del equipo', default=dict, blank=True)
    departamento_destino = models.ForeignKey(
        Departamento, on_delete=models.PROTECT,
        related_name='solicitudes_equipo', verbose_name='Departamento destino',
    )
    estado = models.CharField('Estado', max_length=20, choices=ESTADOS, default='pendiente')
    creado_por = models.ForeignKey(
        Persona, on_delete=models.PROTECT,
        related_name='solicitudes_equipo', verbose_name='Creado por',
    )
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'Solicitud de equipo'
        verbose_name_plural = 'Solicitudes de equipos'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'Solicitud #{self.pk} → {self.departamento_destino} ({self.get_estado_display()})'


class CambioPendiente(models.Model):
    """Cambio de edición/eliminación aplicado y pendiente de aprobación del dueño (D1, D8)."""
    TIPOS = [
        ('edicion', 'Edición'),
        ('eliminacion', 'Eliminación'),
    ]
    ESTADOS = [
        ('pendiente', 'Pendiente'),
        ('aprobado', 'Aprobado'),
        ('cancelado', 'Cancelado'),
    ]
    equipo = models.ForeignKey(
        Equipo, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='cambios_pendientes', verbose_name='Equipo',
    )
    tipo = models.CharField('Tipo', max_length=20, choices=TIPOS)
    snapshot = models.JSONField('Snapshot previo', default=dict, blank=True)
    estado = models.CharField('Estado', max_length=20, choices=ESTADOS, default='pendiente')
    solicitado_por = models.ForeignKey(
        Persona, on_delete=models.PROTECT,
        related_name='cambios_pendientes_solicitados', verbose_name='Solicitado por',
    )
    departamento_dueno = models.ForeignKey(
        Departamento, on_delete=models.PROTECT,
        related_name='cambios_pendientes', verbose_name='Departamento dueño',
    )
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'Cambio pendiente'
        verbose_name_plural = 'Cambios pendientes'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'{self.get_tipo_display()} #{self.pk} — {self.equipo} ({self.get_estado_display()})'


class PartePersona(models.Model):
    parte = models.ForeignKey(
        ParteTrabajo, on_delete=models.CASCADE,
        related_name='personas', verbose_name='Parte de trabajo'
    )
    persona = models.ForeignKey(
        Persona, on_delete=models.CASCADE,
        related_name='partes', verbose_name='Persona'
    )
    horas_trabajadas = models.DecimalField(
        'Horas trabajadas', max_digits=6, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )
    horas_extras = models.DecimalField(
        'Horas extra', max_digits=6, decimal_places=2, default=0,
        validators=[MinValueValidator(0)]
    )

    class Meta:
        verbose_name = 'Persona en parte'
        verbose_name_plural = 'Personas en partes'
        unique_together = ['parte', 'persona']

    def __str__(self):
        return f'{self.persona} - Parte {self.parte_id}'


class VisitaLink(models.Model):
    uuid = models.UUIDField('UUID', unique=True, default=uuid.uuid4, editable=False)
    creado_por = models.ForeignKey(
        'auth.User', on_delete=models.CASCADE,
        related_name='enlaces_visita', verbose_name='Creado por'
    )
    usado = models.BooleanField('Usado', default=False)
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)
    fecha_uso = models.DateTimeField('Fecha de uso', null=True, blank=True)

    class Meta:
        verbose_name = 'Enlace de visita'
        verbose_name_plural = 'Enlaces de visita'
        ordering = ['-fecha_creacion']

    def __str__(self):
        return f'Visita {self.uuid} {"(usado)" if self.usado else "(activo)"}'


class Periodo(models.Model):
    fecha_inicio = models.DateField('Fecha de inicio')
    fecha_fin = models.DateField('Fecha de fin')
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'Periodo'
        verbose_name_plural = 'Periodos'
        ordering = ['-fecha_inicio']

    def __str__(self):
        return f'{self.fecha_inicio:%d/%m/%Y} – {self.fecha_fin:%d/%m/%Y}'

    def total_acciones(self):
        from django.db.models import Sum
        total = Asignacion.objects.filter(
            fecha__gte=self.fecha_inicio, fecha__lte=self.fecha_fin
        ).aggregate(t=Sum('acciones'))['t'] or 0
        total += ParteTrabajo.objects.filter(
            fecha_inicio__gte=self.fecha_inicio, fecha_fin__lte=self.fecha_fin
        ).aggregate(t=Sum('total_acciones'))['t'] or 0
        return total


class Auditoria(models.Model):
    ACCIONES = [
        ('editar', 'Editar'),
        ('eliminar', 'Eliminar'),
    ]

    usuario = models.ForeignKey(
        Persona, on_delete=models.SET_NULL, null=True, blank=True,
        verbose_name='Usuario'
    )
    accion = models.CharField('Acción', max_length=20, choices=ACCIONES)
    modelo = models.CharField('Modelo', max_length=50)
    objeto_id = models.PositiveIntegerField('ID del objeto')
    descripcion = models.TextField('Descripción')
    fecha = models.DateTimeField('Fecha', auto_now_add=True)

    class Meta:
        verbose_name = 'Auditoría'
        verbose_name_plural = 'Auditorías'
        ordering = ['-fecha']

    def __str__(self):
        usuario_str = str(self.usuario) if self.usuario else '—'
        return f'{self.get_accion_display()} {self.modelo} #{self.objeto_id} por {usuario_str}'
