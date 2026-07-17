from django.db import models
from django.core.validators import MinValueValidator


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
