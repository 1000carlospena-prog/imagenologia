web: python manage.py migrate && python manage.py importar_equipos --force && gunicorn imagenologia.wsgi:application --bind 0.0.0.0:$PORT
