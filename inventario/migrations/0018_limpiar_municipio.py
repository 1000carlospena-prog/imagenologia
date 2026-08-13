# Limpieza: elimina el campo texto Equipo.municipio (ya migrado a FK
# en 0017 vía municipio_nuevo) y renombra el temporal a 'municipio'.
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0017_datos_jerarquia_centros'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='equipo',
            name='municipio',
        ),
        migrations.RenameField(
            model_name='equipo',
            old_name='municipio_nuevo',
            new_name='municipio',
        ),
    ]