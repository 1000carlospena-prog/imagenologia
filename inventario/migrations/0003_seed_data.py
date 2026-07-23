from django.db import migrations


def crear_admin_y_personas(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Persona = apps.get_model('inventario', 'Persona')

    if not User.objects.filter(username='rximagenologia').exists():
        User.objects.create_user(
            username='rximagenologia',
            password='59968839',
            is_staff=True,
            is_superuser=True,
        )

    personas_data = [
        ('Carlos', 'Peña'),
        ('Rafael', 'Castillo'),
        ('Carlos', 'Medina'),
    ]
    for nombre, apellido in personas_data:
        Persona.objects.get_or_create(
            nombre=nombre,
            apellido=apellido,
            defaults={'activo': True},
        )


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0002_partetrabajo_partepersona'),
    ]

    operations = [
        migrations.RunPython(crear_admin_y_personas),
    ]
