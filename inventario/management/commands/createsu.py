from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Crea el superusuario por defecto si no existe'

    def handle(self, *args, **options):
        username = '1000carlos'
        email = '1000carlos.pena@gmail.com'
        password = 'Carlos1*'

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username, email, password)
            self.stdout.write(self.style.SUCCESS(f'Superusuario "{username}" creado correctamente.'))
        else:
            self.stdout.write(self.style.WARNING(f'Superusuario "{username}" ya existe.'))
