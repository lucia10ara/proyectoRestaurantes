from django.shortcuts import render, get_object_or_404
from .models import Perfil, Ciudad, Restaurante, Resena, Foto

#DEFINIMOS LAS LISTAS DE LISTAS Y LISTAS DE DETALLES PARA CADA MODELO

#Pagina principal 
def index(request):
    return render(request, 'index.html')


# Restaurantes ---------------
def lista_restaurantes(request):
    restaurantes = Restaurante.objects.all()
    context = {'restaurantes': restaurantes}
    return render(request, 'restaurantes/lista_restaurantes.html', context)


def detalle_restaurante(request, pk):
    restaurante = get_object_or_404(Restaurante, pk=pk)
    context = {'restaurante': restaurante}
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
