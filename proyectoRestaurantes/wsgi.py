"""Configuración WSGI para proyectoRestaurantes."""
import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'proyectoRestaurantes.settings')

application = get_wsgi_application()
