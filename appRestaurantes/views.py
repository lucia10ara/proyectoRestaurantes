from django.db.models import Avg, Count
from django.shortcuts import render, get_object_or_404
from .models import Perfil, Ciudad, Alergeno, Restaurante, Resena, Foto, Comentario


def index(request):
    return render(request, 'index.html')


#---------- Restaurantes ----------
def lista_restaurantes(request):
    #Filtros por GET: ?ciudad=1&ninos=1&perros=1&alergeno=2
    restaurantes = Restaurante.objects.select_related('ciudad').annotate(media=Avg('resenas__puntuacion'))
    ciudad = request.GET.get('ciudad')
    alergeno = request.GET.get('alergeno')
    if ciudad:
        restaurantes = restaurantes.filter(ciudad_id=ciudad)
    if request.GET.get('ninos'):
        restaurantes = restaurantes.filter(admite_ninos=True)
    if request.GET.get('perros'):
        restaurantes = restaurantes.filter(admite_perros=True)
    if alergeno:
        restaurantes = restaurantes.filter(opciones_sin_alergenos__id=alergeno)
    context = {
        'restaurantes': restaurantes,
        'ciudades': Ciudad.objects.all(),
        'alergenos': Alergeno.objects.all(),
        'f_ciudad': ciudad, 'f_alergeno': alergeno,
        'f_ninos': request.GET.get('ninos'), 'f_perros': request.GET.get('perros'),
    }
    return render(request, 'restaurantes/lista_restaurantes.html', context)


def detalle_restaurante(request, pk):
    restaurante = get_object_or_404(Restaurante, pk=pk)
    media = restaurante.resenas.aggregate(media=Avg('puntuacion'))['media']
    context = {
        'restaurante': restaurante,
        'resenas': restaurante.resenas.select_related('autor__usuario'),
        'fotos': restaurante.fotos.annotate(n_likes=Count('likes', distinct=True)),
        'media': media,
    }
    return render(request, 'restaurantes/detalle_restaurante.html', context)


#---------- Reseñas ----------
def lista_resenas(request):
    resenas = Resena.objects.select_related('restaurante', 'autor__usuario')
    return render(request, 'resenas/lista_resenas.html', {'resenas': resenas})


def detalle_resena(request, pk):
    resena = get_object_or_404(Resena, pk=pk)
    context = {
        'resena': resena,
        'fotos': resena.fotos.all(),
        'comentarios': resena.comentarios.select_related('autor__usuario'),
    }
    return render(request, 'resenas/detalle_resena.html', context)


#---------- Fotos ----------
def lista_fotos(request):
    fotos = Foto.objects.select_related('restaurante', 'autor__usuario').annotate(
        n_likes=Count('likes', distinct=True), n_comentarios=Count('comentarios', distinct=True))
    return render(request, 'fotos/lista_fotos.html', {'fotos': fotos})


def detalle_foto(request, pk):
    foto = get_object_or_404(Foto, pk=pk)
    context = {
        'foto': foto,
        'n_likes': foto.likes.count(),
        'quienes_like': foto.likes.select_related('usuario'),
        'comentarios': foto.comentarios.select_related('autor__usuario'),
    }
    return render(request, 'fotos/detalle_foto.html', context)


#---------- Perfiles ----------
def lista_perfiles(request):
    perfiles = Perfil.objects.select_related('usuario')
    return render(request, 'perfiles/lista_perfiles.html', {'perfiles': perfiles})


def detalle_perfil(request, pk):
    #Página de perfil: foto, reseñas, fotos subidas y fotos que le gustan
    perfil = get_object_or_404(Perfil.objects.select_related('usuario', 'ciudad'), pk=pk)
    context = {
        'perfil': perfil,
        'resenas': perfil.resenas.select_related('restaurante'),
        'fotos': perfil.fotos.select_related('restaurante'),
        'fotos_gustadas': perfil.fotos_gustadas.select_related('restaurante'),
        'amigos': perfil.amigos.select_related('usuario'),
        'siguiendo': perfil.siguiendo.select_related('usuario'),
        'seguidores': perfil.seguidores.select_related('usuario'),
    }
    return render(request, 'perfiles/detalle_perfil.html', context)


#---------- Ciudades ----------
def lista_ciudades(request):
    ciudades = Ciudad.objects.annotate(n_restaurantes=Count('restaurantes'))
    return render(request, 'ciudades/lista_ciudades.html', {'ciudades': ciudades})


def detalle_ciudad(request, pk):
    ciudad = get_object_or_404(Ciudad, pk=pk)
    restaurantes = ciudad.restaurantes.annotate(media=Avg('resenas__puntuacion'))
    return render(request, 'ciudades/detalle_ciudad.html', {'ciudad': ciudad, 'restaurantes': restaurantes})
