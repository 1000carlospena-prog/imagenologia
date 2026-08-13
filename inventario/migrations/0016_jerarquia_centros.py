# Esquema jerarquía de centros (Fase 1): Centro, Municipio, SolicitudEquipo,
# CambioPendiente, Departamento.centro, Equipo.eliminado_en + municipio FK
# temporal (municipio_nuevo), 3 flags de Configuracion.
import inventario.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0015_configuracion_persona_contrasena'),
    ]

    operations = [
        migrations.CreateModel(
            name='Centro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=100, unique=True, verbose_name='Nombre')),
                ('tipo', models.CharField(choices=[('provincial', 'Provincial'), ('territorial', 'Territorial')], default='provincial', max_length=20, verbose_name='Tipo')),
                ('centro_padre', models.ForeignKey(blank=True, null=True, on_delete=models.PROTECT, related_name='hijos', to='inventario.centro', verbose_name='Centro padre')),
                ('activo', models.BooleanField(default=True, verbose_name='Activo')),
            ],
            options={
                'verbose_name': 'Centro',
                'verbose_name_plural': 'Centros',
                'ordering': ['nombre'],
            },
        ),
        migrations.CreateModel(
            name='Municipio',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nombre', models.CharField(max_length=200, verbose_name='Nombre')),
                ('centro', models.ForeignKey(on_delete=models.PROTECT, related_name='municipios', to='inventario.centro', verbose_name='Centro')),
            ],
            options={
                'verbose_name': 'Municipio',
                'verbose_name_plural': 'Municipios',
                'ordering': ['nombre'],
                'unique_together': {('centro', 'nombre')},
            },
        ),
        migrations.CreateModel(
            name='SolicitudEquipo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('datos_equipo', models.JSONField(blank=True, default=dict, verbose_name='Datos del equipo')),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('aprobada', 'Aprobada'), ('cancelada', 'Cancelada')], default='pendiente', max_length=20, verbose_name='Estado')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('creado_por', models.ForeignKey(on_delete=models.PROTECT, related_name='solicitudes_equipo', to='inventario.persona', verbose_name='Creado por')),
                ('departamento_destino', models.ForeignKey(on_delete=models.PROTECT, related_name='solicitudes_equipo', to='inventario.departamento', verbose_name='Departamento destino')),
                ('equipo', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='solicitudes', to='inventario.equipo', verbose_name='Equipo creado')),
            ],
            options={
                'verbose_name': 'Solicitud de equipo',
                'verbose_name_plural': 'Solicitudes de equipos',
                'ordering': ['-fecha_creacion'],
            },
        ),
        migrations.CreateModel(
            name='CambioPendiente',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('tipo', models.CharField(choices=[('edicion', 'Edición'), ('eliminacion', 'Eliminación')], max_length=20, verbose_name='Tipo')),
                ('snapshot', models.JSONField(blank=True, default=dict, verbose_name='Snapshot previo')),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('aprobado', 'Aprobado'), ('cancelado', 'Cancelado')], default='pendiente', max_length=20, verbose_name='Estado')),
                ('fecha_creacion', models.DateTimeField(auto_now_add=True, verbose_name='Fecha de creación')),
                ('departamento_dueno', models.ForeignKey(on_delete=models.PROTECT, related_name='cambios_pendientes', to='inventario.departamento', verbose_name='Departamento dueño')),
                ('equipo', models.ForeignKey(blank=True, null=True, on_delete=models.SET_NULL, related_name='cambios_pendientes', to='inventario.equipo', verbose_name='Equipo')),
                ('solicitado_por', models.ForeignKey(on_delete=models.PROTECT, related_name='cambios_pendientes_solicitados', to='inventario.persona', verbose_name='Solicitado por')),
            ],
            options={
                'verbose_name': 'Cambio pendiente',
                'verbose_name_plural': 'Cambios pendientes',
                'ordering': ['-fecha_creacion'],
            },
        ),
        migrations.AddField(
            model_name='departamento',
            name='centro',
            field=models.ForeignKey(blank=True, default=inventario.models.centro_provincial_por_defecto, null=True, on_delete=models.PROTECT, related_name='departamentos', to='inventario.centro', verbose_name='Centro'),
        ),
        migrations.AddField(
            model_name='equipo',
            name='municipio_nuevo',
            field=models.ForeignKey(blank=True, null=True, on_delete=models.PROTECT, related_name='equipos', to='inventario.municipio', verbose_name='Municipio'),
        ),
        migrations.AddField(
            model_name='equipo',
            name='eliminado_en',
            field=models.DateTimeField(blank=True, null=True, verbose_name='Eliminado el'),
        ),
        migrations.AddField(
            model_name='configuracion',
            name='mostrar_aprobaciones',
            field=models.BooleanField(default=False, help_text='Si está activa, el departamento dueño ve y aprueba las solicitudes y cambios pendientes.', verbose_name='Mostrar aprobaciones de cambios'),
        ),
        migrations.AddField(
            model_name='configuracion',
            name='mostrar_ordenes_servicio',
            field=models.BooleanField(default=False, help_text='Si está activa, el módulo de órdenes de servicio se muestra en la navegación.', verbose_name='Mostrar órdenes de servicio'),
        ),
        migrations.AddField(
            model_name='configuracion',
            name='permitir_login_centros_territoriales',
            field=models.BooleanField(default=False, help_text='Si está activa, el login de centro muestra el selector de centros provinciales y territoriales.', verbose_name='Permitir login de centros territoriales'),
        ),
    ]