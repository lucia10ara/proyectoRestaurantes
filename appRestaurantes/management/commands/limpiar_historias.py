"""Borra las historias que ya caducaron (y sus archivos). Las caducadas dejan de verse solas a las 24 h;
esto solo libera espacio. Se puede ejecutar a mano o programar cada día:  python manage.py limpiar_historias"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from appRestaurantes.models import Historia


def borrar_caducadas():
    """Devuelve cuántas historias borró."""
    n = 0
    for historia in Historia.objects.filter(caduca__lte=timezone.now()):
        if historia.imagen:
            historia.imagen.delete(save=False)  #borra también el archivo
        historia.delete()
        n += 1
    return n


class Command(BaseCommand):
    help = "Borra las historias caducadas (más de 24 horas)"

    def handle(self, *args, **opciones):
        self.stdout.write(f"Historias caducadas borradas: {borrar_caducadas()}")
