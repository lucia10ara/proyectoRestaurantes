"""Filtros de restaurantes, compartidos por la lista de Restaurantes y por Explorar (fotos).

Los filtros que miran otras tablas (reseñas, guardados, fotos, alérgenos, tipos de comida) se hacen con
subconsultas "id in (...)": así no se duplican filas ni se deforman las medias de las reseñas.
Los sí/no solo devuelven lo CONFIRMADO: si de un restaurante no sabemos si tiene terraza, no sale al filtrar por terraza.
"""
from django.db.models import Q

from .models import Resena, Guardado, Foto, Restaurante, MomentoComida, Alergeno

#(nombre en la URL, campo del modelo, texto del filtro)
BOOLEANOS = [
    ('terraza', 'terraza', 'Terraza'),
    ('menu', 'menu_del_dia', 'Menú del día'),
    ('vegetariano', 'vegetariano', 'Vegetariano'),
    ('vegano', 'vegano', 'Vegano'),
    ('grupos', 'para_grupos', 'Para grupos'),
    ('accesible', 'accesible', 'Accesible'),
    ('ninos', 'admite_ninos', 'Con niños'),
    ('perros', 'admite_perros', 'Con perro'),
]
#los que van en "Más filtros" (los de siempre, ciudad/alérgeno/niños/perros, se ven a la vista)
AVANZADOS = {'precio', 'precio_max', 'momento', 'terraza', 'menu', 'vegetariano', 'vegano', 'grupos', 'accesible',
             'amigos', 'guardados', 'con_fotos'}


def entero(valor, minimo, maximo):
    try:
        n = int(valor)
    except (TypeError, ValueError):
        return None
    return n if minimo <= n <= maximo else None


def ids_de_restaurantes(params, yo):
    """Subconsultas de ids para los filtros que dependen de otras tablas (o None si no hay ninguna)."""
    subconsultas = []
    if params.get('alergeno'):
        subconsultas.append(Alergeno.restaurantes.through.objects.filter(alergeno_id=entero(params['alergeno'], 1, 10**9)).values('restaurante_id'))
    if params.get('momento'):
        subconsultas.append(MomentoComida.restaurantes.through.objects.filter(momentocomida__clave=params['momento']).values('restaurante_id'))
    if params.get('con_fotos'):
        subconsultas.append(Foto.objects.values('restaurante_id'))
    if yo and params.get('amigos'):  #lo recomienda alguien a quien sigo (le dio 4 o 5 estrellas)
        subconsultas.append(Resena.objects.filter(autor__in=yo.siguiendo.all(), puntuacion__gte=4).values('restaurante_id'))
    if yo and params.get('guardados'):
        subconsultas.append(Guardado.objects.filter(perfil=yo).values('restaurante_id'))
    return subconsultas


def filtrar(qs, params, yo, prefijo=''):
    """Aplica los filtros de la URL. prefijo='' para restaurantes, 'restaurante__' para fotos."""
    p = prefijo
    campo_id = 'restaurante_id' if prefijo else 'pk'

    q = (params.get('q') or '').strip()
    if q:  #buscador: nombre o tipo de cocina (icontains no distingue mayúsculas)
        qs = qs.filter(Q(**{p + 'nombre__icontains': q}) | Q(**{p + 'tipo_cocina__icontains': q}))
    if params.get('comunidad'):
        qs = qs.filter(**{p + 'ciudad__comunidad': params['comunidad']})
    if entero(params.get('ciudad'), 1, 10**9):
        qs = qs.filter(**{p + 'ciudad_id': int(params['ciudad'])})
    if entero(params.get('precio'), 1, 3):
        qs = qs.filter(**{p + 'precio': int(params['precio'])})
    if entero(params.get('precio_max'), 1, 1000):  #los que no tienen precio conocido no salen
        qs = qs.filter(**{p + 'precio_max_persona__lte': int(params['precio_max'])})
    for nombre, campo, _ in BOOLEANOS:
        if params.get(nombre):
            qs = qs.filter(**{p + campo: True})
    for sub in ids_de_restaurantes(params, yo):
        qs = qs.filter(**{campo_id + '__in': sub})
    return qs


def contexto_filtros(params, yo):
    """Lo que necesita la plantilla filtros.html para pintar los filtros avanzados."""
    activos = [k for k in AVANZADOS if params.get(k)]
    return {
        'booleanos': [(n, t) for n, _, t in BOOLEANOS if n not in ('ninos', 'perros')],
        'momentos': MomentoComida.objects.all(),
        'precios': Restaurante.PRECIOS,
        'avanzados_activos': len(activos),
        'con_sesion': bool(yo),
    }
