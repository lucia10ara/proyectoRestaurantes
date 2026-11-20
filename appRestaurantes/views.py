import math
from datetime import date
from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Avg, Count, Max, Min, Q
from django.urls import reverse
from django.db.models.functions import Round
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from .filtros import filtrar, contexto_filtros
from .forms import RegistroForm, VisitaForm
from .models import Perfil, Ciudad, Restaurante, Resena, Foto, Alergeno, Visita, Guardado, Notificacion, Historia, con_foto_destacada
from .notificaciones import notificar
from .recomendaciones import anotar_amigos, amigos_por_restaurante

# Create your views here.

#DEFINIMOS LAS LISTAS DE LISTAS Y LISTAS DE DETALLES PARA CADA MODELO

#Hemos decidido no crear vistas para los modelos Comentario y Alergeno:
# -Comentario: no tiene sentido por si solo, siempre va de una foto o de una reseña así que se consulta desde la vista de detalle de esa foto o reseña
# -Alergeno: solo sirve para etiquetar restaurantes, que es donde se consulta


#ciudades para los desplegables: con miles de pueblos importados, solo salen las que tienen bastantes restaurantes
#(más la que esté elegida, para que no desaparezca del desplegable)
MIN_RESTAURANTES_CIUDAD = 15

def ciudades_principales(elegida=None, comunidad=None):
    ciudades = Ciudad.objects.annotate(n=Count('restaurantes')).order_by('nombre')
    if comunidad:  #con una comunidad elegida salen todas sus ciudades que tengan algún restaurante
        return ciudades.filter(comunidad=comunidad, n__gte=1)
    condicion = Q(n__gte=MIN_RESTAURANTES_CIUDAD)
    if str(elegida or '').isdigit():  #la ciudad llega en la URL: si no es un número se ignora
        condicion |= Q(pk=int(elegida))
    return ciudades.filter(condicion)


#todas las comunidades que hay en la base de datos, para el primer desplegable
def lista_comunidades():
    return (Ciudad.objects.exclude(comunidad__isnull=True).exclude(comunidad='')
            .order_by('comunidad').values_list('comunidad', flat=True).distinct())


#devuelve en JSON las ciudades de una comunidad, para rellenar el segundo desplegable sin recargar la página
def ciudades_comunidad(request):
    comunidad = request.GET.get('comunidad', '')
    datos = [{'id': c.id, 'nombre': c.nombre} for c in ciudades_principales(comunidad=comunidad)] if comunidad else []
    return JsonResponse(datos, safe=False)


#perfil del usuario que ha iniciado sesión (None si no ha entrado o si es un usuario sin perfil, p. ej. creado a mano en el admin)
def perfil_actual(request):
    if request.user.is_authenticated:
        return Perfil.objects.select_related('ciudad').filter(usuario=request.user).first()
    return None


#Registro: crea el usuario y su perfil, y lo deja con la sesión iniciada
def registro(request):
    if request.user.is_authenticated:
        return redirect('index')
    form = RegistroForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        usuario = form.save()
        login(request, usuario)
        return redirect('index')
    return render(request, 'registration/registro.html', {'form': form})


#Seguir / dejar de seguir a un perfil (solo POST y solo con sesión iniciada)
@login_required
@require_POST
def seguir(request, pk):
    yo = perfil_actual(request)
    otro = get_object_or_404(Perfil, pk=pk)
    if yo and yo != otro:  #no se puede seguir a uno mismo
        if yo.siguiendo.filter(pk=otro.pk).exists():
            yo.siguiendo.remove(otro)
        else:
            yo.siguiendo.add(otro)
            hay_aviso = Notificacion.objects.filter(destinatario=otro, actor=yo, tipo='seguidor', leida=False).exists()
            if not hay_aviso:  #seguir y dejar de seguir muchas veces no llena de avisos
                notificar(otro, yo, 'seguidor', f'{yo} ha empezado a seguirte.', reverse('detalle_perfil', args=[yo.pk]))
    return redirect('detalle_perfil', pk=pk)


#Pagina principal: portada con cifras, los restaurantes mejor valorados (tarjetas lado a lado), últimas fotos y reseñas
def index(request):
    yo = perfil_actual(request)

    #pestañas del feed: "Siguiendo" (publicaciones mías y de a quien sigo) o "Descubrir" (de todos).
    #Sin sesión, o si todavía no sigo a nadie, se enseña Descubrir
    ids_siguiendo = list(yo.siguiendo.values_list('id', flat=True)) + [yo.id] if yo else []
    sigo_a_alguien = len(ids_siguiendo) > 1
    modo = 'siguiendo' if (yo and sigo_a_alguien and request.GET.get('vista') != 'descubrir') else 'descubrir'

    fotos = (Foto.objects.select_related('autor__usuario', 'restaurante__ciudad')
             .annotate(num_likes=Count('likes', distinct=True), num_comentarios=Count('comentarios', distinct=True)))
    resenas = (Resena.objects.select_related('autor__usuario', 'restaurante__ciudad')
               .annotate(num_comentarios=Count('comentarios', distinct=True)))
    if modo == 'siguiendo':
        fotos, resenas = fotos.filter(autor_id__in=ids_siguiendo), resenas.filter(autor_id__in=ids_siguiendo)

    #el feed mezcla fotos y reseñas, de lo más nuevo a lo más antiguo
    fotos, resenas = list(fotos[:15]), list(resenas[:15])
    for f in fotos:
        f.tipo_post = 'foto'
    for r in resenas:
        r.tipo_post = 'resena'
    publicaciones = sorted(fotos + resenas, key=lambda p: (p.fecha, p.id), reverse=True)[:20]

    me_gustan = set(yo.fotos_gustadas.values_list('id', flat=True)) if yo else set()
    amigos_ids = set(yo.amigos.values_list('id', flat=True)) if yo else set()
    for p in publicaciones:
        p.me_gusta = p.tipo_post == 'foto' and p.id in me_gustan
        p.es_amigo = p.autor_id in amigos_ids  #para poner la etiqueta "amigo"

    #columna derecha: gente a la que seguir y restaurantes mejor valorados (solo los que ya tienen reseñas)
    sugeridos = Perfil.objects.select_related('usuario', 'ciudad').exclude(id__in=ids_siguiendo).order_by('?')[:5]
    destacados = (con_foto_destacada(Restaurante.objects.filter(resenas__isnull=False)).select_related('ciudad')
                  .annotate(media=Avg('resenas__puntuacion'), num_resenas=Count('resenas', distinct=True))
                  .order_by('-media', '-num_resenas')[:4])

    #tira de historias activas: la mía y las de a quien sigo; primero las que aún no he visto
    tira = []
    if yo:
        vistas = set(yo.historias_vistas.values_list('id', flat=True))
        por_autor = {}
        for h in Historia.activas().filter(autor_id__in=ids_siguiendo).select_related('autor__usuario'):
            datos = por_autor.setdefault(h.autor_id, {'perfil': h.autor, 'sin_ver': 0, 'mia': h.autor_id == yo.id})
            datos['sin_ver'] += 0 if (h.id in vistas or datos['mia']) else 1
        tira = sorted(por_autor.values(), key=lambda d: (not d['mia'], d['sin_ver'] == 0, d['perfil'].usuario.username))

    context = {
        'mi_perfil': yo,
        'tira_historias': tira,
        'modo': modo,
        'sigo_a_alguien': sigo_a_alguien,
        'publicaciones': publicaciones,
        'sugeridos': sugeridos,
        'destacados': destacados,
        #mosaico de la bienvenida: las 4 últimas fotos de los usuarios
        'fotos_portada': [] if yo else list(Foto.objects.select_related('restaurante__ciudad')[:4]),
        #cifras (para la bienvenida de quien no ha entrado)
        'total_restaurantes': Restaurante.objects.count(),
        'total_resenas': Resena.objects.count(),
        'total_fotos': Foto.objects.count(),
    }
    return render(request, 'index.html', context)


#Explorar: rejilla con todas las fotos y filtros (ciudad, niños, perros, alérgenos)
def explorar(request):
    fotos = Foto.objects.select_related('restaurante__ciudad').annotate(num_likes=Count('likes'))

    #los filtros llegan en la URL, por ejemplo /explorar/?ciudad=1&ninos=1
    #solo guardamos los que traen algo (un select sin elegir llega vacío)
    filtros = {k: v for k, v in request.GET.items() if v}

    #si el usuario tiene ciudad y entra sin filtros, le enseñamos primero las fotos de su ciudad
    #(para ver todas elige "Todas las ciudades": llega ?ciudad= vacío y no se aplica el valor por defecto)
    yo = perfil_actual(request)
    ciudad_propia = None
    if not request.GET and yo and yo.ciudad_id:
        ciudad_propia = yo.ciudad
        filtros['ciudad'] = str(yo.ciudad_id)

    ciudad = filtros.get('ciudad')
    tipo = filtros.get('tipo')
    #filtros del restaurante de la foto (los mismos que en la lista de restaurantes, ver filtros.py)
    fotos = filtrar(fotos, filtros, yo, prefijo='restaurante__')
    if tipo:
        fotos = fotos.filter(tipo=tipo)

    context = {
        **contexto_filtros(filtros, yo),
        'fotos': fotos,
        'comunidades': lista_comunidades(),
        'ciudades': ciudades_principales(ciudad, filtros.get('comunidad')),
        'alergenos': Alergeno.objects.all(),
        'tipos': Foto.TIPOS,
        'filtros': filtros,  #para dejar marcados los filtros elegidos
        'ciudad_propia': ciudad_propia,  #solo si estamos aplicando la ciudad del usuario por defecto
    }
    return render(request, 'explorar.html', context)


# Restaurantes ---------------
def lista_restaurantes(request):
    yo = perfil_actual(request)
    restaurantes = con_foto_destacada(Restaurante.objects.select_related('ciudad'))

    q = request.GET.get('q', '').strip()

    #buscador y filtros (llegan en la URL igual que en explorar): primero se filtra y después se calculan las medias
    restaurantes = filtrar(restaurantes, request.GET, yo)

    #añadimos la nota media y el número de reseñas a cada restaurante
    restaurantes = restaurantes.annotate(
        media=Avg('resenas__puntuacion'), num_resenas=Count('resenas', distinct=True)
    ).annotate(estrellas=Round('media'))  #estrellas = media redondeada, para pintarlas

    #orden: por nota (por defecto) o por nombre
    if request.GET.get('orden') == 'nombre':
        restaurantes = restaurantes.order_by('nombre')
    else:
        restaurantes = restaurantes.order_by('-media', 'nombre')

    #paginación: 24 por página (con decenas de miles de restaurantes no se pueden pintar todos de golpe)
    page_obj = Paginator(restaurantes, 24).get_page(request.GET.get('page'))
    page_obj.object_list = anotar_amigos(yo, page_obj)  #«han estado: ...» en cada tarjeta
    filtros = {k: v for k, v in request.GET.items() if v and k != 'page'}

    context = {
        **contexto_filtros(filtros, yo),
        'page_obj': page_obj,
        'comunidades': lista_comunidades(),
        'ciudades': ciudades_principales(request.GET.get('ciudad'), request.GET.get('comunidad')),
        'alergenos': Alergeno.objects.all(),
        'filtros': filtros,
        'q': q,
        'querystring': urlencode(filtros),  #para que los enlaces de página conserven búsqueda y filtros
    }
    return render(request, 'restaurantes/lista_restaurantes.html', context)


# Mapa ---------------
LIMITE_MAPA = 400  #máximo de restaurantes que se mandan al navegador de una vez (al acercar el mapa salen los demás)


def numero(valor, minimo, maximo):
    """float de la URL, o None si no es un número válido dentro del rango (rechaza nan e infinito)."""
    try:
        n = float(valor)
    except (TypeError, ValueError):
        return None
    return n if math.isfinite(n) and minimo <= n <= maximo else None


def con_ubicacion(request):
    """Restaurantes que se pueden poner en el mapa (los que tienen coordenadas) y cumplen los filtros de la URL."""
    base = Restaurante.objects.filter(latitud__isnull=False, longitud__isnull=False)
    return filtrar(base, request.GET, perfil_actual(request))


def mapa(request):
    """Página del mapa: los mismos filtros que la lista de restaurantes. Los puntos los pide el JavaScript a mapa_datos."""
    yo = perfil_actual(request)
    filtros = {k: v for k, v in request.GET.items() if v and k != 'foco'}
    context = {
        **contexto_filtros(filtros, yo),
        'comunidades': lista_comunidades(),
        'ciudades': ciudades_principales(request.GET.get('ciudad'), request.GET.get('comunidad')),
        'alergenos': Alergeno.objects.all(),
        'filtros': filtros,
        'q': request.GET.get('q', '').strip(),
        'querystring': urlencode(filtros),
        'foco': numero(request.GET.get('foco'), 1, 10**9),
    }
    return render(request, 'mapa.html', context)


def mapa_datos(request):
    """JSON para el mapa.
    ?inicial=1 -> solo la zona que ocupan los resultados (para encuadrar el mapa) y el restaurante al que enfocar (?foco=).
    ?sur=&oeste=&norte=&este= -> los restaurantes de esa zona (máximo LIMITE_MAPA) con su nota media."""
    qs = con_ubicacion(request)

    if request.GET.get('inicial'):
        zona = qs.aggregate(sur=Min('latitud'), norte=Max('latitud'), oeste=Min('longitud'), este=Max('longitud'), total=Count('pk'))
        foco_id = numero(request.GET.get('foco'), 1, 10**9)
        foco = Restaurante.objects.filter(pk=int(foco_id), latitud__isnull=False, longitud__isnull=False).first() if foco_id else None
        return JsonResponse({
            'total': zona['total'],
            'zona': None if not zona['total'] else [[zona['sur'], zona['oeste']], [zona['norte'], zona['este']]],
            'foco': {'id': foco.id, 'lat': foco.latitud, 'lon': foco.longitud} if foco else None,
        })

    sur, norte = numero(request.GET.get('sur'), -90, 90), numero(request.GET.get('norte'), -90, 90)
    oeste, este = numero(request.GET.get('oeste'), -180, 180), numero(request.GET.get('este'), -180, 180)
    if None in (sur, norte, oeste, este):
        return JsonResponse({'error': 'Faltan los límites del mapa'}, status=400)
    qs = qs.filter(latitud__range=(sur, norte), longitud__range=(oeste, este))

    total = qs.count()
    lista = list(qs.select_related('ciudad').order_by('pk')[:LIMITE_MAPA])
    amigos = amigos_por_restaurante(perfil_actual(request), [r.id for r in lista])
    notas = {f['restaurante_id']: f for f in Resena.objects.filter(restaurante__in=lista)
             .values('restaurante_id').annotate(media=Avg('puntuacion'), n=Count('id'))}
    return JsonResponse({
        'total': total,
        'restaurantes': [{
            'id': r.id, 'nombre': r.nombre, 'cocina': r.tipo_cocina, 'ciudad': r.ciudad.nombre,
            'direccion': r.direccion_visible, 'lat': r.latitud, 'lon': r.longitud,
            'media': round(notas[r.id]['media'], 1) if r.id in notas else None,
            'resenas': notas[r.id]['n'] if r.id in notas else 0,
            'amigos': amigos.get(r.id, ''),  #quién de los que sigo ha estado (vacío si nadie)
            'url': reverse('detalle_restaurante', args=[r.id]),
        } for r in lista],
    })


def gente_en_restaurante(yo, restaurante):
    """Qué personas a las que sigo tienen relación con este restaurante, separado por tipo.
    'Han estado' son SOLO visitas confirmadas; publicar o recomendar no es haber estado."""
    sigo = list(yo.siguiendo.values_list('id', flat=True))
    if not sigo:
        return {'sigo_a_alguien': False}
    amigos = set(yo.amigos.values_list('id', flat=True))

    def una_por_persona(filas, perfil_de, detalle_de):
        vistos, lista = set(), []
        for fila in filas:
            perfil = perfil_de(fila)
            if perfil.id not in vistos:
                vistos.add(perfil.id)
                lista.append({'perfil': perfil, 'detalle': detalle_de(fila), 'amigo': perfil.id in amigos})
        return lista

    visitas = Visita.objects.filter(restaurante=restaurante, perfil_id__in=sigo).select_related('perfil__usuario').order_by('-fecha')
    recomiendan = Resena.objects.filter(restaurante=restaurante, autor_id__in=sigo, puntuacion__gte=4).select_related('autor__usuario')
    guardados = Guardado.objects.filter(restaurante=restaurante, perfil_id__in=sigo).select_related('perfil__usuario')

    #han publicado: fotos y reseñas juntas, contando cuántas de cada una
    publicado = {}
    for f in Foto.objects.filter(restaurante=restaurante, autor_id__in=sigo).select_related('autor__usuario'):
        publicado.setdefault(f.autor_id, {'perfil': f.autor, 'fotos': 0, 'resenas': 0})['fotos'] += 1
    for r in Resena.objects.filter(restaurante=restaurante, autor_id__in=sigo).select_related('autor__usuario'):
        publicado.setdefault(r.autor_id, {'perfil': r.autor, 'fotos': 0, 'resenas': 0})['resenas'] += 1

    def texto_publicado(d):
        partes = []
        if d['fotos']:
            partes.append(f"{d['fotos']} foto{'s' if d['fotos'] > 1 else ''}")
        if d['resenas']:
            partes.append(f"{d['resenas']} reseña{'s' if d['resenas'] > 1 else ''}")
        return ' y '.join(partes)

    return {
        'sigo_a_alguien': True,
        'estado': una_por_persona(visitas, lambda v: v.perfil, lambda v: f"estuvo el {v.fecha:%d/%m/%Y}"),
        'recomiendan': una_por_persona(recomiendan, lambda r: r.autor, lambda r: f"le dio {r.puntuacion} estrellas"),
        'pendiente': una_por_persona(guardados, lambda g: g.perfil, lambda g: "lo tiene guardado"),
        'publicado': [{'perfil': d['perfil'], 'detalle': texto_publicado(d), 'amigo': d['perfil'].id in amigos} for d in publicado.values()],
    }


def detalle_restaurante(request, pk):
    restaurante = get_object_or_404(Restaurante, pk=pk)
    media = restaurante.resenas.aggregate(media=Avg('puntuacion'))['media']  #nota media del restaurante
    estrellas = round(media) if media else 0  #redondeada para pintar las estrellas
    yo = perfil_actual(request)

    #medias por categoría (solo cuentan las reseñas que tienen esa nota; las antiguas no la tienen)
    medias = restaurante.resenas.aggregate(
        **{'media_' + campo: Avg(campo) for campo, _ in Resena.CATEGORIAS},
        con_detalle=Count('id', filter=Q(nota_comida__isnull=False)))
    categorias = []
    for campo, nombre in Resena.CATEGORIAS:
        valor = medias['media_' + campo]
        categorias.append({'nombre': nombre, 'media': valor, 'porcentaje': round(valor / 5 * 100) if valor else 0})

    context = {
        'restaurante': restaurante, 'media': media, 'estrellas': estrellas,
        'categorias': categorias if medias['con_detalle'] else [],
        'con_detalle': medias['con_detalle'],
        'social': gente_en_restaurante(yo, restaurante) if yo else None,
        #lo mío con este restaurante: si lo tengo guardado y mis visitas confirmadas
        'guardado': bool(yo) and restaurante.guardados.filter(perfil=yo).exists(),
        'mis_visitas': list(restaurante.visitas.filter(perfil=yo)[:5]) if yo else [],
        'mis_colecciones': list(yo.colecciones.all()) if yo else [],
        'en_colecciones': list(yo.colecciones.filter(elementos__restaurante=restaurante)) if yo else [],
        'visita_form': VisitaForm(initial={'fecha': date.today()}),
        'hoy': date.today(),
    }
    return render(request, 'restaurantes/detalle_restaurante.html', context)


# Reseñas ---------------------
def lista_resenas(request):
    resenas = Resena.objects.all()
    context = {'resenas': resenas}
    return render(request, 'resenas/lista_resenas.html', context)


def detalle_resena(request, pk):
    resena = get_object_or_404(Resena, pk=pk)
    context = {'resena': resena}
    return render(request, 'resenas/detalle_resena.html', context)


# Fotos --------------------
def lista_fotos(request):
    fotos = Foto.objects.all()
    context = {'fotos': fotos}
    return render(request, 'fotos/lista_fotos.html', context)


def detalle_foto(request, pk):
    foto = get_object_or_404(Foto, pk=pk)
    yo = perfil_actual(request)
    context = {'foto': foto, 'me_gusta': bool(yo) and foto.likes.filter(pk=yo.pk).exists()}  #para pintar el botón de me gusta
    return render(request, 'fotos/detalle_foto.html', context)


#Perfiles -----------------------------
def lista_perfiles(request):
    perfiles = Perfil.objects.all()
    context = {'perfiles': perfiles}
    return render(request, 'perfiles/lista_perfiles.html', context)


def detalle_perfil(request, pk):
    perfil = get_object_or_404(Perfil, pk=pk)
    yo = perfil_actual(request)
    colecciones = perfil.colecciones.all() if (yo == perfil or request.user.is_staff) else perfil.colecciones.filter(publica=True)
    context = {
        'perfil': perfil,
        'n_colecciones': colecciones.count(),
        'es_el_mio': yo == perfil,
        'lo_sigo': bool(yo) and yo.siguiendo.filter(pk=perfil.pk).exists(),
        'me_sigue': bool(yo) and perfil.siguiendo.filter(pk=yo.pk).exists(),  #si además me sigue, somos amigos
    }
    return render(request, 'perfiles/detalle_perfil.html', context)


#Ciudades -----------------------------------
def lista_ciudades(request):
    ciudades = ciudades_principales()
    context = {'ciudades': ciudades}
    return render(request, 'ciudades/lista_ciudades.html', context)


def detalle_ciudad(request, pk):
    ciudad = get_object_or_404(Ciudad, pk=pk)
    context = {'ciudad': ciudad}
    return render(request, 'ciudades/detalle_ciudad.html', context)
