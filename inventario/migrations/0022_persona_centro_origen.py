# Personas específicas por centro: centro_origen indica el centro (provincial o
# territorial) donde se creó la persona; el territorial no ve las personas del
# padre ni viceversa.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0021_centro_municipios_departamentocentro'),
    ]

    operations = [
        migrations.AddField(
            model_name='persona',
            name='centro_origen',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='personas_origen', to='inventario.centro', verbose_name='Centro donde se creó la persona'),
        ),
    ]