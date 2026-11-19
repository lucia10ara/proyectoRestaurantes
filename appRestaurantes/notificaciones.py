"""Crear avisos para los usuarios y contarlos (el contador sale en el menú de todas las páginas)."""
from .models import Notificacion


def notificar(destinatario, actor, tipo, texto, url=''):
    """Crea un aviso. Nadie se avisa a sí mismo."""
    if actor is not None and destinatario.id == actor.id:
        return None
    return Notificacion.objects.create(destinatario=destinatario, actor=actor, tipo=tipo, texto=texto[:250], url=url)


def contexto_avisos(request):
    """Context processor: número de avisos sin leer del usuario que ha entrado (0 si no hay sesión)."""
    if not request.user.is_authenticated:
        return {'avisos_sin_leer': 0}
    return {'avisos_sin_leer': Notificacion.objects.filter(destinatario__usuario=request.user, leida=False).count()}
