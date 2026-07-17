from django.db import migrations, models
import django.core.validators
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Persona',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, verbose_name='Nombre')),
                ('apellido', models.CharField(max_length=100, verbose_name='Apellido')),
                ('email', models.EmailField(blank=True, max_length=254, null=True, verbose_name='Correo electrónico')),
                ('telefono', models.CharField(blank=True, max_length=20, null=True, verbose_name='Teléfono')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True, verbose_name='Última actualización')),
            ],
            options={
                'verbose_name': 'Persona',
                'verbose_name_plural': 'Personas',
                'ordering': ['apellido', 'nombre'],
            },
        ),
        migrations.CreateModel(
            name='OrdenTrabajo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('numero_orden', models.CharField(max_length=50, unique=True, verbose_name='N° de Orden')),
                ('descripcion', models.TextField(blank=True, verbose_name='Descripción')),
                ('fecha', models.DateField(verbose_name='Fecha')),
                ('completada', models.BooleanField(default=False, verbose_name='Completada')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('fecha_actualizacion', models.DateTimeField(auto_now=True, verbose_name='Última actualización')),
            ],
            options={
                'verbose_name': 'Orden de Trabajo',
                'verbose_name_plural': 'Órdenes de Trabajo',
                'ordering': ['-fecha', '-fecha_creacion'],
            },
        ),
        migrations.CreateModel(
            name='Asignacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField(verbose_name='Fecha')),
                ('acciones', models.PositiveIntegerField(default=0, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Acciones')),
                ('horas_diurnas', models.DecimalField(decimal_places=2, default=0, max_digits=6, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Horas diurnas')),
                ('horas_extras', models.DecimalField(decimal_places=2, default=0, max_digits=6, validators=[django.core.validators.MinValueValidator(0)], verbose_name='Horas extra')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('orden_trabajo', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asignaciones', to='inventario.ordentrabajo', verbose_name='Orden de Trabajo')),
                ('persona', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='asignaciones', to='inventario.persona', verbose_name='Persona')),
            ],
            options={
                'verbose_name': 'Asignación',
                'verbose_name_plural': 'Asignaciones',
                'ordering': ['-fecha', 'persona__apellido', 'persona__nombre'],
                'unique_together': {('orden_trabajo', 'persona', 'fecha')},
            },
        ),
    ]
