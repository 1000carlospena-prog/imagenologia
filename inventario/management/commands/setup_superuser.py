from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Crea superadmin v1 y elimina otros superusuarios'

    def handle(self, *args, **options):
        v1, created = User.objects.get_or_create(username='v1')
        if created:
            v1.set_password('Carlos1*')
            v1.is_superuser = True
            v1.is_staff = True
            v1.save()
            self.stdout.write(self.style.SUCCESS('Superusuario "v1" creado.'))
        else:
            v1.set_password('Carlos1*')
            if not v1.is_superuser:
                v1.is_superuser = True
                v1.is_staff = True
            v1.save()
            self.stdout.write(self.style.WARNING('Superusuario "v1" ya existe, contraseña actualizada.'))

        for user in User.objects.filter(is_superuser=True).exclude(username='v1'):
            user.is_superuser = False
            user.is_staff = False
            user.save()
            self.stdout.write(f'Superusuario "{user.username}" desactivado.')

        remaining = User.objects.filter(is_superuser=True).count()
        self.stdout.write(self.style.SUCCESS(f'Total superusuarios activos: {remaining} ("v1").'))