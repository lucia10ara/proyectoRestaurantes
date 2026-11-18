from django.contrib.auth.models import User
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Pone una contraseña de prueba a los usuarios que no pueden iniciar sesión (los cargados con el fixture de ejemplo).'

    def add_arguments(self, parser):
        parser.add_argument('password', nargs='?', default='restaurantes123')

    def handle(self, *args, **opciones):
        cambiados = []
        for u in User.objects.all():
            if not u.has_usable_password():  #no tocamos a los que ya tienen contraseña (p. ej. el superusuario)
                u.set_password(opciones['password'])
                u.save()
                cambiados.append(u.username)
        self.stdout.write(self.style.SUCCESS(f"Contraseña '{opciones['password']}' puesta a: {', '.join(cambiados) or 'nadie'}"))
