"""Descubre: Para ti (recomendaciones), Novedades, Joyas ocultas y la Ruleta. Todo con los filtros de siempre (filtros.py)."""
import random
from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render, redirect

from .filtros import filtrar, contexto_filtros, entero
from .models import Alergeno, Restaurante
from .recomendaciones import para_ti as calcular_para_ti, ids_joyas, con_notas, anotar_amigos
from .views import perfil_actual, lista_comunidades, ciudades_principales
from .views_social import perfil_o_403


def contexto_con_filtros(request, yo, filtros):
    """Lo que necesita filtros.html (igual que en la lista de restaurantes)."""
    return {
        **contexto_filtros(filtros, yo),
        'comunidades': lista_comunidades(),
        'ciudades': ciudades_principales(filtros.get('ciudad'), filtros.get('comunidad')),
        'alergenos': Alergeno.objects.all(),
        'filtros': filtros,
        'querystring': urlencode(filtros),
    }


def descubre(request):
    return redirect('para_ti' if request.user.is_authenticated else 'novedades')


def recomendados_con_amigos(yo):
    lista = calcular_para_ti(yo)
    anotar_amigos(yo, [r for r, _ in lista])  #pone el atributo en los mismos objetos
    return lista


@login_required
def para_ti(request):
    yo = perfil_o_403(request)
    return render(request, 'descubre/para_ti.html', {'seccion': 'para_ti', 'recomendados': recomendados_con_amigos(yo), 'yo': yo})


def listado(request, seccion, qs, titulo, ayuda, orden):
    """Página de tarjetas con filtros y paginación, común a Novedades y Joyas."""
    yo = perfil_actual(request)
    filtros = {k: v for k, v in request.GET.items() if v and k != 'page'}
    qs = con_notas(filtrar(qs, filtros, yo)).order_by(*orden)
    pagina = Paginator(qs, 24).get_page(request.GET.get('page'))
    pagina.object_list = anotar_amigos(yo, pagina)
    return render(request, 'descubre/lista.html', {
        **contexto_con_filtros(request, yo, filtros), 'seccion': seccion, 'lista': pagina, 'titulo': titulo, 'ayuda': ayuda})


def novedades(request):
    #solo los que tienen fecha de alta: los importados antes de que existiera ese dato no se sabe cuándo se añadieron
    return listado(request, 'novedades', Restaurante.objects.filter(fecha_alta__isnull=False),
                   'Novedades', 'Los últimos restaurantes añadidos a la app.', ('-fecha_alta', '-id'))


def joyas(request):
    return listado(request, 'joyas', Restaurante.objects.filter(id__in=ids_joyas()),
                   'Joyas ocultas', 'Muy bien valorados (4,5 o más de media) pero poco conocidos: entre 2 y 10 reseñas.',
                   ('-media', '-num_resenas'))


def ruleta(request):
    """Elige un restaurante al azar entre los que cumplen los filtros. Hace falta acotar por ciudad o comunidad."""
    yo = perfil_actual(request)
    filtros = {k: v for k, v in request.GET.items() if v and k not in ('girar', 'excluir')}
    ciudad_propia = None
    if not request.GET and yo and yo.ciudad_id:  #al entrar, su ciudad ya elegida
        filtros['ciudad'] = str(yo.ciudad_id)
        ciudad_propia = yo.ciudad

    elegido, aviso, hay = None, None, 0
    if request.GET.get('girar'):
        if not (filtros.get('ciudad') or filtros.get('comunidad')):
            aviso = 'Elige al menos una comunidad o una ciudad para girar la ruleta.'
        else:
            qs = filtrar(Restaurante.objects.all(), filtros, yo)
            anterior = entero(request.GET.get('excluir'), 1, 10**9)
            hay = qs.count()
            if anterior and hay > 1:  #que no repita el que acaba de salir
                qs, hay = qs.exclude(pk=anterior), hay - 1
            if hay:
                pk = qs.order_by('pk')[random.randrange(hay)].pk  #posición al azar, sin ordenar toda la tabla
                elegido = con_notas(Restaurante.objects.filter(pk=pk)).first()
                anotar_amigos(yo, [elegido])
            else:
                aviso = 'No hay ningún restaurante con esos filtros. Prueba con menos.'
    otra_vez = urlencode({**filtros, 'girar': 1, **({'excluir': elegido.pk} if elegido else {})})
    return render(request, 'descubre/ruleta.html', {
        **contexto_con_filtros(request, yo, filtros), 'seccion': 'ruleta', 'girar': True, 'texto_boton': 'Girar la ruleta',
        'elegido': elegido, 'aviso': aviso, 'otra_vez': otra_vez, 'ciudad_propia': ciudad_propia})
