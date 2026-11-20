"""Borra las historias que ya caducaron (y sus archivos). Las caducadas dejan de verse solas a las 24 h y además se borran
solas cada vez que alguien publica una historia; este comando solo sirve para forzarlo:  python manage.py limpiar_historias"""
from django.core.management.base import BaseCommand

from appRestaurantes.models import Historia


class Command(BaseCommand):
    help = "Borra las historias caducadas (más de 24 horas)"

    def handle(self, *args, **opciones):
        self.stdout.write(f"Historias caducadas borradas: {Historia.borrar_caducadas()}")
