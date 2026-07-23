import os
os.environ['DJANGO_SECRET_KEY'] = 'test'
os.environ['DJANGO_SETTINGS_MODULE'] = 'imagenologia.settings'
import django
django.setup()
from django.conf import settings
db = settings.DATABASES['default']
print(f'Engine: {db["ENGINE"]}')
print(f'Name: {db["NAME"]}')
print(f'Host: {db.get("HOST", "")}')
print(f'User: {db.get("USER", "")}')
print(f'Port: {db.get("PORT", "")}')
