"""Página de avisos (notificaciones) del usuario que ha entrado."""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect
from django.views.decorators.http import require_POST

from .models import Notificacion
from .views_social import perfil_o_403


@login_required
def avisos(request):
    yo = perfil_o_403(request)
    pagina = Paginator(yo.notificaciones.select_related('actor__usuario'), 20).get_page(request.GET.get('page'))
    nuevos = {n.id for n in pagina if not n.leida}  #para resaltarlos esta vez
    #al abrir la página se marcan como leídos los que se están viendo (no los de otras páginas)
    Notificacion.objects.filter(id__in=nuevos).update(leida=True)
    return render(request, 'avisos.html', {'lista': pagina, 'nuevos': nuevos})


@login_required
@require_POST
def avisos_borrar_leidos(request):
    perfil_o_403(request).notificaciones.filter(leida=True).delete()
    return redirect('avisos')
