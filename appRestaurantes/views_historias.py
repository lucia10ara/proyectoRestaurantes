"""Historias de 24 horas. Las ven su autor y quienes lo siguen; crear y borrar: el autor (borrar también la administradora)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect

from django.views.decorators.http import require_POST

from .forms import HistoriaForm
from .models import Historia, Perfil, Restaurante
from .views import perfil_actual
from .views_social import perfil_o_403

MAX_HISTORIAS_ACTIVAS = 10  #por persona, para que nadie llene la tira


@login_required
def crear_historia(request, pk):
    restaurante = get_object_or_404(Restaurante, pk=pk)
    yo = perfil_o_403(request)
    form = HistoriaForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and Historia.activas().filter(autor=yo).count() >= MAX_HISTORIAS_ACTIVAS:
        form.add_error(None, f'Ya tienes {MAX_HISTORIAS_ACTIVAS} historias activas. Espera a que caduquen o borra alguna.')
    elif form.is_valid():
        historia = form.save(commit=False)
        historia.autor, historia.restaurante = yo, restaurante
        historia.save()
        messages.success(request, 'Historia publicada: la verán tus seguidores durante 24 horas.')
        return redirect('ver_historias', pk=yo.pk)
    return render(request, 'formulario.html', {
        'titulo': f'Historia en {restaurante.nombre}', 'form': form, 'boton': 'Publicar historia', 'multipart': True,
        'volver_texto': restaurante.nombre, 'volver_url': 'detalle_restaurante', 'volver_pk': restaurante.pk})


def ver_historias(request, pk):
    """Las historias activas de una persona, de una en una (?n=0, 1, 2...)."""
    autor = get_object_or_404(Perfil.objects.select_related('usuario'), pk=pk)
    yo = perfil_actual(request)
    if not yo:
        return redirect(f"/login/?next={request.path}")
    historias = [h for h in Historia.activas().filter(autor=autor).select_related('restaurante__ciudad')
                 if h.visible_para(yo, request.user)]
    if not historias:
        raise Http404
    try:
        n = min(max(int(request.GET.get('n', 0)), 0), len(historias) - 1)
    except ValueError:
        n = 0
    historia = historias[n]
    es_mia = yo.id == autor.id
    if not es_mia:
        historia.vista_por.add(yo)  #para el aro de "sin ver" y el contador del autor
    return render(request, 'historias/ver_historias.html', {
        'autor': autor, 'historia': historia, 'n': n, 'total': len(historias),
        'anterior': n - 1 if n > 0 else None, 'siguiente': n + 1 if n < len(historias) - 1 else None,
        'es_mia': es_mia, 'vistas': historia.vista_por.select_related('usuario') if es_mia else None,
        'caduca_en': historia.caduca, 'rayas': range(len(historias)),
    })


@login_required
@require_POST
def borrar_historia(request, pk):
    historia = get_object_or_404(Historia, pk=pk)
    yo = perfil_o_403(request)
    if not (request.user.is_staff or historia.autor_id == yo.id):
        raise PermissionDenied
    if historia.imagen:
        historia.imagen.delete(save=False)
    historia.delete()
    messages.success(request, 'Historia borrada.')
    return redirect('index')
