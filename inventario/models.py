from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone


class Persona(models.Model):
    nombre = models.CharField('Nombre', max_length=100)
    apellido = models.CharField('Apellido', max_length=100)
    email = models.EmailField('Correo electrónico', blank=True, null=True)
    telefono = models.CharField('Teléfono', max_length=20, blank=True, null=True)
    activo = models.BooleanField('Activo', default=True)
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)
    fecha_actualizacion = models.DateTimeField('Última actualización', auto_now=True)

    class Meta:
        verbose_name = 'Persona'
        verbose_name_plural = 'Personas'
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f'{self.nombre} {self.apellido}'

    def total_acciones(self):
        return self.asignaciones.aggregate(total=models.Sum('acciones'))['total'] or 0

    def total_horas_diurnas(self):
        return self.asignaciones.aggregate(total=models.Sum('horas_diurnas'))['total'] or 0

    def total_horas_extras(self):
        return self.asignaciones.aggregate(total=models.Sum('horas_extras'))['total'] or 0


class OrdenTrabajo(models.Model):
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

    def total_acciones(self):
        return self.asignaciones.aggregate(total=models.Sum('acciones'))['total'] or 0

    def total_horas(self):
        aggr = self.asignaciones.aggregate(
            diurnas=models.Sum('horas_diurnas'),
            extras=models.Sum('horas_extras'),
        )
        return (aggr['diurnas'] or 0) + (aggr['extras'] or 0)

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


class Equipo(models.Model):
    TIPO_CHOICES = [
        ('RX', 'Rayos X'),
        ('USD', 'Ultrasonido'),
        ('OTRO', 'Otro'),
    ]
    ESTADO_CHOICES = [
        ('Funcionando', 'Funcionando'),
        ('Afectado', 'Afectado'),
        ('Roto', 'Roto'),
    ]

    municipio = models.CharField('Municipio', max_length=200)
    unidad_salud = models.CharField('Unidad de salud', max_length=300)
    tipo = models.CharField('Tipo', max_length=50, choices=TIPO_CHOICES, default='OTRO')
    denominacion = models.CharField('Denominación', max_length=300, blank=True)
    servicio = models.CharField('Servicio', max_length=200, blank=True)
    local = models.CharField('Local', max_length=200, blank=True)
    marca = models.CharField('Marca', max_length=200, blank=True)
    modelo = models.CharField('Modelo', max_length=200, blank=True)
    numero_serie = models.CharField('N° de Serie', max_length=200, blank=True)
    estado = models.CharField('Estado', max_length=50, choices=ESTADO_CHOICES, blank=True)
    observaciones = models.TextField('Observaciones', blank=True)
    frecuencia = models.CharField('Frecuencia de mantenimiento', max_length=100, blank=True)
    fuente = models.CharField('Archivo fuente', max_length=100, blank=True)
    fecha_creacion = models.DateTimeField('Fecha de creación', auto_now_add=True)

    class Meta:
        verbose_name = 'Equipo'
        verbose_name_plural = 'Equipos'
        ordering = ['municipio', 'unidad_salud', 'denominacion']

    def __str__(self):
        return f'{self.denominacion or self.tipo} - {self.unidad_salud} ({self.municipio})'


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
