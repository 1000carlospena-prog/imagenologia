import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = 'Crea el superusuario por defecto si no existe'

    def add_arguments(self, parser):
        parser.add_argument('--password', type=str, help='Contraseña del superusuario')

    def handle(self, *args, **options):
        username = os.environ.get('DJANGO_SU_USER', '1000carlos')
        email = os.environ.get('DJANGO_SU_EMAIL', '1000carlos.pena@gmail.com')
        password = options['password'] or os.environ.get('DJANGO_SU_PASSWORD')

        if not password:
            raise CommandError('Debes definir DJANGO_SU_PASSWORD en el entorno o usar --password')

        if not User.objects.filter(username=username).exists():
            User.objects.create_superuser(username, email, password)
            self.stdout.write(self.style.SUCCESS(f'Superusuario "{username}" creado correctamente.'))
        else:
            self.stdout.write(self.style.WARNING(f'Superusuario "{username}" ya existe.'))
