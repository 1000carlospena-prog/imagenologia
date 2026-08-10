from django.contrib.auth.hashers import make_password
from django.db import migrations


def asignar_imagenologia(apps, schema_editor):
    Departamento = apps.get_model('inventario', 'Departamento')
    departamento, _ = Departamento.objects.get_or_create(
        nombre='Imagenología',
        defaults={'contrasena': make_password('imagenologia2026')},
    )
    for model_name in ('Persona', 'Equipo', 'OrdenTrabajo', 'ParteTrabajo'):
        Model = apps.get_model('inventario', model_name)
        Model.objects.filter(departamento__isnull=True).update(departamento=departamento)


def revertir(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0013_departamento_equipo_departamento_and_more'),
    ]

    operations = [
        migrations.RunPython(asignar_imagenologia, revertir),
    ]