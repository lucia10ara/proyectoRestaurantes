from datetime import date
from urllib.parse import urlencode
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Avg, Count, Q
from django.db.models.functions import Round
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from .filtros import filtrar, contexto_filtros
from .forms import RegistroForm, VisitaForm
from .models import Perfil, Ciudad, Restaurante, Resena, Foto, Alergeno, Visita, Guardado

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
    destacados = (Restaurante.objects.filter(resenas__isnull=False).select_related('ciudad')
                  .annotate(media=Avg('resenas__puntuacion'), num_resenas=Count('resenas', distinct=True))
                  .order_by('-media', '-num_resenas')[:4])

    context = {
        'mi_perfil': yo,
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
    restaurantes = Restaurante.objects.select_related('ciudad')

    #buscador: busca el texto en el nombre o en el tipo de cocina (icontains no distingue mayúsculas)
    q = request.GET.get('q', '').strip()
    if q:
        restaurantes = restaurantes.filter(Q(nombre__icontains=q) | Q(tipo_cocina__icontains=q))

    #filtros (llegan en la URL igual que en explorar): primero se filtra y después se calculan las medias
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
    context = {
        'perfil': perfil,
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
