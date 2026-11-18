from django.db.models import Avg, Count, Q
from django.db.models.functions import Round
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from .forms import RegistroForm
from .models import Perfil, Ciudad, Restaurante, Resena, Foto, Alergeno

# Create your views here.

#DEFINIMOS LAS LISTAS DE LISTAS Y LISTAS DE DETALLES PARA CADA MODELO

#Hemos decidido no crear vistas para los modelos Comentario y Alergeno:
# -Comentario: no tiene sentido por si solo, siempre va de una foto o de una reseña así que se consulta desde la vista de detalle de esa foto o reseña
# -Alergeno: solo sirve para etiquetar restaurantes, que es donde se consulta


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
    #los restaurantes mejor valorados (Avg calcula la media de las puntuaciones de sus reseñas)
    #estrellas = media redondeada, para pintarlas (igual que en la lista de restaurantes)
    destacados = (Restaurante.objects.select_related('ciudad')
                  .annotate(media=Avg('resenas__puntuacion'), num_resenas=Count('resenas', distinct=True))
                  .annotate(estrellas=Round('media'))
                  .order_by('-media', 'nombre')[:6])

    #select_related trae los datos relacionados de golpe para no hacer muchas consultas
    ultimas_fotos = Foto.objects.select_related('restaurante').annotate(num_likes=Count('likes'))[:8]

    #si hay sesión, el feed son las fotos de la gente a la que sigo (los amigos son seguidos mutuos, así que ya están incluidos)
    yo = perfil_actual(request)
    feed = []
    if yo:
        amigos_ids = set(yo.amigos.values_list('id', flat=True))
        feed = list(Foto.objects.filter(autor__in=yo.siguiendo.all())
                    .select_related('autor__usuario', 'restaurante').annotate(num_likes=Count('likes'))[:12])
        for foto in feed:
            foto.es_amigo = foto.autor_id in amigos_ids  #para poner la etiqueta "amigo" en la plantilla

    context = {
        'mi_perfil': yo,
        'feed': feed,
        'destacados': destacados,
        'ultimas_fotos': ultimas_fotos,
        'ultimas_resenas': Resena.objects.select_related('autor__usuario', 'restaurante')[:4],
        'perfiles': Perfil.objects.select_related('usuario')[:5],
        #cifras de la portada
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
    alergeno = filtros.get('alergeno')
    tipo = filtros.get('tipo')
    if ciudad:
        fotos = fotos.filter(restaurante__ciudad_id=ciudad)
    if filtros.get('ninos'):
        fotos = fotos.filter(restaurante__admite_ninos=True)
    if filtros.get('perros'):
        fotos = fotos.filter(restaurante__admite_perros=True)
    if alergeno:
        fotos = fotos.filter(restaurante__opciones_sin_alergenos=alergeno)
    if tipo:
        fotos = fotos.filter(tipo=tipo)

    context = {
        'fotos': fotos.distinct(),
        'ciudades': Ciudad.objects.all(),
        'alergenos': Alergeno.objects.all(),
        'tipos': Foto.TIPOS,
        'filtros': filtros,  #para dejar marcados los filtros elegidos
        'ciudad_propia': ciudad_propia,  #solo si estamos aplicando la ciudad del usuario por defecto
    }
    return render(request, 'explorar.html', context)


# Restaurantes ---------------
def lista_restaurantes(request):
    #añadimos la nota media y el número de reseñas a cada restaurante
    restaurantes = Restaurante.objects.select_related('ciudad').annotate(
        media=Avg('resenas__puntuacion'), num_resenas=Count('resenas', distinct=True)
    ).annotate(estrellas=Round('media'))  #estrellas = media redondeada, para pintarlas

    #buscador: busca el texto en el nombre o en el tipo de cocina (icontains no distingue mayúsculas)
    q = request.GET.get('q', '').strip()
    if q:
        restaurantes = restaurantes.filter(Q(nombre__icontains=q) | Q(tipo_cocina__icontains=q))

    #filtros (llegan en la URL igual que en explorar)
    if request.GET.get('ciudad'):
        restaurantes = restaurantes.filter(ciudad_id=request.GET['ciudad'])
    if request.GET.get('ninos'):
        restaurantes = restaurantes.filter(admite_ninos=True)
    if request.GET.get('perros'):
        restaurantes = restaurantes.filter(admite_perros=True)
    if request.GET.get('alergeno'):
        restaurantes = restaurantes.filter(opciones_sin_alergenos=request.GET['alergeno'])

    #orden: por nota (por defecto) o por nombre
    if request.GET.get('orden') == 'nombre':
        restaurantes = restaurantes.order_by('nombre')
    else:
        restaurantes = restaurantes.order_by('-media', 'nombre')

    context = {
        'restaurantes': restaurantes.distinct(),
        'ciudades': Ciudad.objects.all(),
        'alergenos': Alergeno.objects.all(),
        'filtros': {k: v for k, v in request.GET.items() if v},
        'q': q,
    }
    return render(request, 'restaurantes/lista_restaurantes.html', context)


def detalle_restaurante(request, pk):
    restaurante = get_object_or_404(Restaurante, pk=pk)
    media = restaurante.resenas.aggregate(media=Avg('puntuacion'))['media']  #nota media del restaurante
    estrellas = round(media) if media else 0  #redondeada para pintar las estrellas
    context = {'restaurante': restaurante, 'media': media, 'estrellas': estrellas}
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
    context = {'foto': foto}
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
    ciudades = Ciudad.objects.all()
    context = {'ciudades': ciudades}
    return render(request, 'ciudades/lista_ciudades.html', context)


def detalle_ciudad(request, pk):
    ciudad = get_object_or_404(Ciudad, pk=pk)
    context = {'ciudad': ciudad}
    return render(request, 'ciudades/detalle_ciudad.html', context)
