"""Colecciones: listas temáticas de restaurantes. Crear, editar, añadir y quitar restaurantes: solo su dueño
(la administradora también puede borrar). Las privadas las ve solo su dueño; para los demás no existen (404)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Avg, Count
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST

from .forms import ColeccionForm
from .models import Coleccion, ElementoColeccion, Perfil, Restaurante, Resena
from .views import perfil_actual
from .views_social import perfil_o_403, volver

MAX_COLECCIONES = 50  #por usuario
MAX_RESTAURANTES = 200  #por colección


def coleccion_visible(request, pk):
    """La colección si el usuario puede verla; si no, 404 (no se revela que existe)."""
    coleccion = get_object_or_404(Coleccion.objects.select_related('perfil__usuario'), pk=pk)
    if not coleccion.visible_para(perfil_actual(request), request.user):
        raise Http404
    return coleccion


def coleccion_mia(request, pk):
    """La colección solo si es del usuario que ha entrado."""
    coleccion = get_object_or_404(Coleccion.objects.select_related('perfil__usuario'), pk=pk)
    if coleccion.perfil_id != perfil_o_403(request).id:
        raise PermissionDenied
    return coleccion


@login_required
def crear_coleccion(request):
    yo = perfil_o_403(request)
    form = ColeccionForm(request.POST or None, perfil=yo)
    if request.method == 'POST' and yo.colecciones.count() >= MAX_COLECCIONES:
        form.add_error(None, f'Has llegado al máximo de {MAX_COLECCIONES} colecciones.')
    elif form.is_valid():
        coleccion = form.save(commit=False)
        coleccion.perfil = yo
        coleccion.save()
        messages.success(request, 'Colección creada.')
        return redirect('detalle_coleccion', pk=coleccion.pk)
    return render(request, 'formulario.html', {'titulo': 'Nueva colección', 'form': form, 'boton': 'Crear colección',
                  'volver_texto': 'mi perfil', 'volver_url': 'detalle_perfil', 'volver_pk': yo.pk})


@login_required
def editar_coleccion(request, pk):
    coleccion = coleccion_mia(request, pk)
    form = ColeccionForm(request.POST or None, instance=coleccion, perfil=coleccion.perfil)
    if form.is_valid():
        form.save()
        messages.success(request, 'Colección guardada.')
        return redirect('detalle_coleccion', pk=pk)
    return render(request, 'formulario.html', {'titulo': 'Editar colección', 'form': form, 'boton': 'Guardar cambios',
                  'volver_texto': coleccion.nombre, 'volver_url': 'detalle_coleccion', 'volver_pk': pk})


@login_required
@require_POST
def borrar_coleccion(request, pk):
    coleccion = get_object_or_404(Coleccion, pk=pk)
    yo = perfil_o_403(request)
    if not (request.user.is_staff or coleccion.perfil_id == yo.id):
        raise PermissionDenied
    duenio = coleccion.perfil_id
    coleccion.delete()
    messages.success(request, 'Colección borrada.')
    return redirect('detalle_perfil', pk=duenio)


def detalle_coleccion(request, pk):
    coleccion = coleccion_visible(request, pk)
    yo = perfil_actual(request)
    elementos = list(coleccion.elementos.select_related('restaurante__ciudad'))
    notas = {n['restaurante_id']: n for n in Resena.objects.filter(restaurante_id__in=[e.restaurante_id for e in elementos])
             .values('restaurante_id').annotate(media=Avg('puntuacion'), n=Count('id'))}
    for e in elementos:  #lo que necesita la tarjeta de restaurante: media, número de reseñas y estrellas
        r = e.restaurante
        dato = notas.get(r.id)
        r.media = dato['media'] if dato else None
        r.num_resenas = dato['n'] if dato else 0
        r.estrellas = round(r.media) if r.media else 0
    return render(request, 'colecciones/detalle_coleccion.html', {
        'coleccion': coleccion, 'elementos': elementos,
        'es_mia': bool(yo) and yo.id == coleccion.perfil_id,
        'con_ubicacion': any(e.restaurante.latitud is not None for e in elementos),
    })


def colecciones_de_perfil(request, pk):
    perfil = get_object_or_404(Perfil.objects.select_related('usuario'), pk=pk)
    yo = perfil_actual(request)
    es_mio = bool(yo) and yo.id == perfil.id
    colecciones = perfil.colecciones.annotate(n=Count('elementos'))
    if not es_mio and not request.user.is_staff:
        colecciones = colecciones.filter(publica=True)
    return render(request, 'colecciones/lista_colecciones.html', {'perfil': perfil, 'colecciones': colecciones, 'es_mio': es_mio})


@login_required
@require_POST
def anadir_a_coleccion(request, pk):
    """Desde la ficha del restaurante: lo añade a una colección mía o crea una nueva con el nombre indicado."""
    restaurante = get_object_or_404(Restaurante, pk=pk)
    yo = perfil_o_403(request)
    destino = volver(request, redirect('detalle_restaurante', pk=pk))
    nueva = request.POST.get('nombre_nueva', '').strip()
    if nueva:
        if len(nueva) > 80:
            messages.error(request, 'El nombre de la colección es demasiado largo (máximo 80 letras).')
            return destino
        coleccion = yo.colecciones.filter(nombre__iexact=nueva).first()
        if not coleccion:
            if yo.colecciones.count() >= MAX_COLECCIONES:
                messages.error(request, f'Has llegado al máximo de {MAX_COLECCIONES} colecciones.')
                return destino
            coleccion = Coleccion.objects.create(perfil=yo, nombre=nueva)
    else:
        elegida = request.POST.get('coleccion', '')
        coleccion = yo.colecciones.filter(pk=int(elegida)).first() if elegida.isdigit() else None
        if not coleccion:
            messages.error(request, 'Elige una colección o escribe el nombre de una nueva.')
            return destino
    if coleccion.elementos.count() >= MAX_RESTAURANTES:
        messages.error(request, f'Esa colección ya tiene {MAX_RESTAURANTES} restaurantes.')
        return destino
    _, creado = ElementoColeccion.objects.get_or_create(coleccion=coleccion, restaurante=restaurante)
    messages.success(request, f'Añadido a «{coleccion.nombre}».' if creado else f'Ya estaba en «{coleccion.nombre}».')
    return destino


@login_required
@require_POST
def quitar_de_coleccion(request, pk, restaurante_pk):
    coleccion = coleccion_mia(request, pk)
    coleccion.elementos.filter(restaurante_id=restaurante_pk).delete()
    messages.success(request, 'Quitado de la colección.')
    return redirect('detalle_coleccion', pk=pk)


@login_required
@require_POST
def nota_en_coleccion(request, pk, restaurante_pk):
    coleccion = coleccion_mia(request, pk)
    elemento = get_object_or_404(coleccion.elementos, restaurante_id=restaurante_pk)
    elemento.nota = request.POST.get('nota', '').strip()[:200]
    elemento.save(update_fields=['nota'])
    return redirect('detalle_coleccion', pk=pk)
