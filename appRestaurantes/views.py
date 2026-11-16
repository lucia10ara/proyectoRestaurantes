from django.db.models import Avg, Count, Q
from django.db.models.functions import Round
from django.shortcuts import render, get_object_or_404
from .models import Perfil, Ciudad, Restaurante, Resena, Foto, Alergeno

# Create your views here.

#DEFINIMOS LAS LISTAS DE LISTAS Y LISTAS DE DETALLES PARA CADA MODELO

#Hemos decidido no crear vistas para los modelos Comentario y Alergeno:
# -Comentario: no tiene sentido por si solo, siempre va de una foto o de una reseña así que se consulta desde la vista de detalle de esa foto o reseña
# -Alergeno: solo sirve para etiquetar restaurantes, que es donde se consulta


#Pagina principal (estilo red social: "stories" de restaurantes arriba y un feed de fotos)
def index(request):
    #stories: los restaurantes mejor valorados (Avg calcula la media de las puntuaciones de sus reseñas)
    destacados = (Restaurante.objects.annotate(media=Avg('resenas__puntuacion'))
                  .order_by('-media', 'nombre')[:10])

    #feed: las fotos más recientes con su autor, restaurante y comentarios
    #select_related y prefetch_related traen los datos relacionados de golpe para no hacer muchas consultas
    publicaciones = (Foto.objects.select_related('autor__usuario', 'restaurante', 'resena')
                     .prefetch_related('comentarios__autor__usuario', 'likes')[:12])

    context = {
        'destacados': destacados,
        'publicaciones': publicaciones,
        'ultimas_resenas': Resena.objects.select_related('autor__usuario', 'restaurante')[:3],
        'perfiles': Perfil.objects.select_related('usuario')[:5],
    }
    return render(request, 'index.html', context)


#Explorar: rejilla con todas las fotos y filtros (ciudad, niños, perros, alérgenos)
def explorar(request):
    fotos = Foto.objects.select_related('restaurante__ciudad').annotate(num_likes=Count('likes'))

    #los filtros llegan en la URL, por ejemplo /explorar/?ciudad=1&ninos=1
    ciudad = request.GET.get('ciudad')
    alergeno = request.GET.get('alergeno')
    tipo = request.GET.get('tipo')
    if ciudad:
        fotos = fotos.filter(restaurante__ciudad_id=ciudad)
    if request.GET.get('ninos'):
        fotos = fotos.filter(restaurante__admite_ninos=True)
    if request.GET.get('perros'):
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
        'filtros': request.GET,  #para dejar marcados los filtros elegidos
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
        'filtros': request.GET,
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
    context = {'perfil': perfil}
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
