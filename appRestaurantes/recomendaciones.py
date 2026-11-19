"""Recomendaciones "Para ti", joyas ocultas y ruleta. Siempre explican POR QUÉ salen (nada de cajas negras).
Nunca recomiendan lo que el usuario ya ha visitado, guardado o reseñado, y respetan sus preferencias (niños, perro)."""
from collections import Counter

from django.db.models import Avg, Count, Q
from django.db.models.functions import Round

from .models import Resena, Restaurante

#una joya oculta: muy bien valorada pero poco conocida (varias reseñas, no una sola)
JOYA_MIN_RESENAS, JOYA_MAX_RESENAS, JOYA_MIN_MEDIA = 2, 10, 4.5
NOTA_MINIMA_POPULARES = 3.5  #para el plan B de "Para ti"
NOTA_MINIMA_AFINES = 3  #para los de la misma cocina que le gusta al usuario


def con_notas(qs):
    """Añade lo que necesita la tarjeta de restaurante: media, número de reseñas y estrellas redondeadas."""
    return (qs.select_related('ciudad')
            .annotate(media=Avg('resenas__puntuacion'), num_resenas=Count('resenas', distinct=True))
            .annotate(estrellas=Round('media')))


def segun_preferencias(qs, yo):
    """Quita lo que no encaja con lo que el usuario dijo que suele necesitar."""
    if yo.lleva_perros:
        qs = qs.filter(admite_perros=True)
    if yo.lleva_ninos:
        qs = qs.filter(admite_ninos=True)
    return qs


def ids_ya_conocidos(yo):
    """Restaurantes que el usuario ya visitó, guardó o reseñó: no se le recomiendan."""
    return (set(yo.visitas.values_list('restaurante_id', flat=True))
            | set(yo.guardados.values_list('restaurante_id', flat=True))
            | set(yo.resenas.values_list('restaurante_id', flat=True)))


def lista_nombres(nombres):
    nombres = list(dict.fromkeys(nombres))  #sin repetir, en orden
    if len(nombres) <= 2:
        return ' y '.join(nombres)
    return f'{nombres[0]}, {nombres[1]} y {len(nombres) - 2} más'


def para_ti(yo, limite=12):
    """[(restaurante, [motivos])] de mayor a menor puntuación. Combina lo que recomienda la gente a la que sigo,
    la cocina que le gusta al usuario y su ciudad."""
    conocidos = ids_ya_conocidos(yo)
    puntos, motivos = Counter(), {}

    def anotar(rid, p, motivo):
        puntos[rid] += p
        motivos.setdefault(rid, []).append(motivo)

    #1) lo que recomiendan (4 o 5 estrellas) las personas a las que sigo
    por_restaurante = {}
    recomendadas = (Resena.objects.filter(autor__in=yo.siguiendo.all(), puntuacion__gte=4)
                    .exclude(restaurante_id__in=conocidos).select_related('autor__usuario').order_by('-fecha', '-id')[:500])
    for r in recomendadas:
        por_restaurante.setdefault(r.restaurante_id, []).append(r.autor.usuario.username)
    for rid, nombres in por_restaurante.items():
        anotar(rid, 3 * min(len(set(nombres)), 3), f'Lo recomienda {lista_nombres(nombres)}')

    #2) la cocina que le gusta (donde ha estado o puntuado con 4-5 estrellas), en su ciudad
    gustados = set(yo.visitas.values_list('restaurante_id', flat=True)) | set(
        yo.resenas.filter(puntuacion__gte=4).values_list('restaurante_id', flat=True))
    if gustados and yo.ciudad_id:
        cocinas = Counter(Restaurante.objects.filter(id__in=gustados).values_list('tipo_cocina', flat=True))
        favoritas = [c for c, _ in cocinas.most_common(3)]
        parecidos = segun_preferencias(Restaurante.objects.filter(ciudad_id=yo.ciudad_id, tipo_cocina__in=favoritas), yo)
        afines = con_notas(parecidos.exclude(id__in=conocidos)).filter(Q(media__isnull=True) | Q(media__gte=NOTA_MINIMA_AFINES))
        for r in afines.order_by('-media', '-num_resenas')[:30]:  #los mal valorados no se recomiendan; los aún sin reseñas sí pueden salir
            anotar(r.id, 2, f'Te gusta la cocina «{r.tipo_cocina}»')

    #3) pequeños empujones: es de su ciudad y está bien valorado
    candidatos = set(puntos)
    if candidatos:
        for r in con_notas(Restaurante.objects.filter(id__in=candidatos)):
            if yo.ciudad_id and r.ciudad_id == yo.ciudad_id:
                anotar(r.id, 1, f'En {r.ciudad.nombre}')
            if r.media and r.media >= 4:
                anotar(r.id, 1, f'Nota media {r.media:.1f}'.replace('.', ','))

    elegidos = [rid for rid, _ in puntos.most_common(limite * 2)]
    restaurantes = {r.id: r for r in segun_preferencias(con_notas(Restaurante.objects.filter(id__in=elegidos)), yo)}
    resultado = [(restaurantes[rid], motivos[rid]) for rid in elegidos if rid in restaurantes][:limite]

    if not resultado:  #sin nada que cruzar todavía: lo mejor valorado de su ciudad
        base = Restaurante.objects.filter(resenas__isnull=False).exclude(id__in=conocidos)
        if yo.ciudad_id:
            base = base.filter(ciudad_id=yo.ciudad_id)
        #solo los bien valorados: no se recomienda un sitio con mala nota aunque no haya nada más
        populares = con_notas(segun_preferencias(base, yo)).filter(media__gte=NOTA_MINIMA_POPULARES).order_by('-media', '-num_resenas')[:limite]
        donde = f' en {yo.ciudad.nombre}' if yo.ciudad_id else ''
        resultado = [(r, [f'Popular{donde}']) for r in populares]
    return resultado


def ids_joyas():
    """Restaurantes muy bien valorados pero con pocas reseñas."""
    filas = (Resena.objects.values('restaurante_id').annotate(m=Avg('puntuacion'), n=Count('id'))
             .filter(n__gte=JOYA_MIN_RESENAS, n__lte=JOYA_MAX_RESENAS, m__gte=JOYA_MIN_MEDIA))
    return [f['restaurante_id'] for f in filas]
