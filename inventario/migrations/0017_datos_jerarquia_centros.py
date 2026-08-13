# Datos idempotentes de la jerarquía de centros: centro provincial
# 'Santiago de Cuba' (D2), departamentos sin centro → provincial, y
# Equipo.municipio (texto) → Municipio FK vía municipio_nuevo, SIN pérdida
# (los textos se conservan hasta 0018). Reverse = noop (D6).
from django.db import migrations


def migrar_datos(apps, schema_editor):
    Centro = apps.get_model('inventario', 'Centro')
    Municipio = apps.get_model('inventario', 'Municipio')
    Departamento = apps.get_model('inventario', 'Departamento')
    Equipo = apps.get_model('inventario', 'Equipo')

    centro_provincial, _ = Centro.objects.get_or_create(
        nombre='Santiago de Cuba',
        defaults={'tipo': 'provincial'},
    )

    # Departamentos sin centro → provincial (idempotente)
    Departamento.objects.filter(centro__isnull=True).update(centro=centro_provincial)

    # Equipo.municipio (texto) → FK municipio_nuevo, solo donde falta (idempotente)
    for equipo in Equipo.objects.filter(municipio_nuevo__isnull=True):
        nombre = (equipo.municipio or '').strip()
        if not nombre:
            continue
        municipio, _ = Municipio.objects.get_or_create(
            nombre=nombre,
            defaults={'centro': equipo.departamento.centro or centro_provincial},
        )
        Equipo.objects.filter(pk=equipo.pk).update(municipio_nuevo=municipio)


def revertir(apps, schema_editor):
    # Noop: el texto original sigue intacto en Equipo.municipio hasta 0018.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0016_jerarquia_centros'),
    ]

    operations = [
        migrations.RunPython(migrar_datos, revertir),
    ]