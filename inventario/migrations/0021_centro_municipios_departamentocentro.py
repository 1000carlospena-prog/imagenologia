# Centros territoriales: municipios que atiende (M2M) y contraseñas locales
# de los departamentos del centro padre (DepartamentoCentro).

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('inventario', '0020_servicio_ordenes'),
    ]

    operations = [
        migrations.AddField(
            model_name='centro',
            name='municipios_atendidos',
            field=models.ManyToManyField(blank=True, related_name='centros_que_atienden', to='inventario.municipio', verbose_name='Municipios que atiende'),
        ),
        migrations.CreateModel(
            name='DepartamentoCentro',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('contrasena', models.CharField(max_length=255, verbose_name='Contraseña')),
                ('centro', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='departamentos_contrasena', to='inventario.centro', verbose_name='Centro')),
                ('departamento', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='contrasenas_por_centro', to='inventario.departamento', verbose_name='Departamento')),
            ],
            options={
                'verbose_name': 'Contraseña de departamento en centro',
                'verbose_name_plural': 'Contraseñas de departamentos por centro',
                'unique_together': {('departamento', 'centro')},
            },
        ),
    ]