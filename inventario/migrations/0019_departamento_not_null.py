# Fix de instalaciones nuevas (fresh installs): tras 0014 asignar valores a los
# 4 campos departamento (Persona, Equipo, OrdenTrabajo, ParteTrabajo), se vuelven
# NOT NULL con su default de modelo. En BDs ya migradas el ALTER es no-op.
# Necesario porque 0013 ya no usa el default callable que consultaba la BD.

import django.db.models.deletion
import inventario.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0018_limpiar_municipio'),
    ]

    operations = [
        migrations.AlterField(
            model_name='equipo',
            name='departamento',
            field=models.ForeignKey(default=inventario.models.departamento_por_defecto, on_delete=django.db.models.deletion.PROTECT, related_name='equipos', to='inventario.departamento', verbose_name='Departamento'),
        ),
        migrations.AlterField(
            model_name='ordentrabajo',
            name='departamento',
            field=models.ForeignKey(default=inventario.models.departamento_por_defecto, on_delete=django.db.models.deletion.PROTECT, related_name='ordenes_trabajo', to='inventario.departamento', verbose_name='Departamento'),
        ),
        migrations.AlterField(
            model_name='partetrabajo',
            name='departamento',
            field=models.ForeignKey(default=inventario.models.departamento_por_defecto, on_delete=django.db.models.deletion.PROTECT, related_name='partes', to='inventario.departamento', verbose_name='Departamento'),
        ),
        migrations.AlterField(
            model_name='persona',
            name='departamento',
            field=models.ForeignKey(default=inventario.models.departamento_por_defecto, on_delete=django.db.models.deletion.PROTECT, related_name='personas', to='inventario.departamento', verbose_name='Departamento'),
        ),
    ]