# Servicio de órdenes por departamento: el módulo de órdenes de servicio
# (acciones, horas, partes) es un servicio SOLO de Imagenología y de los
# departamentos que se activen explícitamente; los demás ven solo integrantes.

import django.db.models.deletion  # noqa
from django.db import migrations, models


def activar_imagenologia(apps, schema_editor):
    Departamento = apps.get_model('inventario', 'Departamento')
    Departamento.objects.filter(nombre__iexact='Imagenología').update(servicio_ordenes=True)


def revertir(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0019_departamento_not_null'),
    ]

    operations = [
        migrations.AddField(
            model_name='departamento',
            name='servicio_ordenes',
            field=models.BooleanField(default=False, help_text='Si está activa, el departamento usa el módulo de órdenes de servicio (acciones, horas, partes).', verbose_name='Servicio de órdenes'),
        ),
        migrations.RunPython(activar_imagenologia, revertir),
    ]