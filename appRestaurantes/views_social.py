from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .forms import ResenaForm, FotoForm, ComentarioForm, RestauranteForm
from .models import Perfil, Restaurante, Resena, Foto, Comentario
from .views import perfil_actual

# ======================================================================
#  PUBLICAR Y MODERAR (usuarios con sesión) · EDITAR Y PANEL (administradora)
#  Reglas: publicar, dar like y comentar -> cualquier usuario con sesión.
#          editar/borrar reseñas, fotos y comentarios -> su dueño o la administradora (is_staff).
#          editar restaurantes y ver el panel -> solo la administradora.
# ======================================================================


#el perfil del usuario o error 403 (un usuario creado a mano en el admin puede no tener perfil)
def perfil_o_403(request):
    yo = perfil_actual(request)
    if not yo:
        raise PermissionDenied("Tu usuario no tiene perfil.")
    return yo


#puede borrar/editar el dueño del contenido o la administradora
def exigir_gestion(request, autor):
    if not (request.user.is_staff or autor.usuario_id == request.user.id):
        raise PermissionDenied


def exigir_staff(request):
    if not request.user.is_staff:
        raise PermissionDenied


# Publicar ---------------------------------------------------------
#primer paso de publicar: buscar el restaurante y elegir si es reseña o foto
@login_required
def publicar(request):
    q = request.GET.get('q', '').strip()
    yo = perfil_o_403(request)
    if len(q) >= 2:
        titulo, restaurantes = 'Resultados', Restaurante.objects.filter(nombre__icontains=q).select_related('ciudad')[:12]
    elif yo.ciudad_id:  #sin búsqueda, sugerimos los más comentados de su ciudad
        titulo = f'Populares en {yo.ciudad.nombre}'
        restaurantes = (Restaurante.objects.filter(ciudad=yo.ciudad).select_related('ciudad')
                        .annotate(n=Count('resenas')).order_by('-n', 'nombre')[:8])
    else:
        titulo, restaurantes = '', []
    return render(request, 'publicar.html', {'q': q, 'titulo_lista': titulo, 'restaurantes': restaurantes})


# Reseñas ---------------------------------------------------------
@login_required
def crear_resena(request, pk):
    restaurante = get_object_or_404(Restaurante, pk=pk)
    yo = perfil_o_403(request)
    form = ResenaForm(request.POST or None)
    if form.is_valid():
        resena = form.save(commit=False)
        resena.restaurante, resena.autor = restaurante, yo  #el autor es siempre el usuario que ha entrado
        resena.save()
        messages.success(request, 'Reseña publicada.')
        return redirect('detalle_resena', pk=resena.pk)
    return render(request, 'formulario.html', {
        'titulo': f'Reseña de {restaurante.nombre}', 'form': form, 'boton': 'Publicar reseña',
        'volver_texto': restaurante.nombre, 'volver_url': 'detalle_restaurante', 'volver_pk': restaurante.pk})


@login_required
def editar_resena(request, pk):
    resena = get_object_or_404(Resena, pk=pk)
    exigir_gestion(request, resena.autor)
    form = ResenaForm(request.POST or None, instance=resena)
    if form.is_valid():
        form.save()
        messages.success(request, 'Reseña actualizada.')
        return redirect('detalle_resena', pk=resena.pk)
    return render(request, 'formulario.html', {
        'titulo': 'Editar reseña', 'form': form, 'boton': 'Guardar cambios',
        'volver_texto': 'la reseña', 'volver_url': 'detalle_resena', 'volver_pk': resena.pk})


@login_required
@require_POST
def borrar_resena(request, pk):
    resena = get_object_or_404(Resena, pk=pk)
    exigir_gestion(request, resena.autor)
    restaurante_id = resena.restaurante_id
    resena.delete()
    messages.success(request, 'Reseña eliminada.')
    return redirect('detalle_restaurante', pk=restaurante_id)


# Fotos -----------------------------------------------------------
@login_required
def subir_foto(request, pk):
    restaurante = get_object_or_404(Restaurante, pk=pk)
    yo = perfil_o_403(request)
    form = FotoForm(request.POST or None, request.FILES or None, restaurante=restaurante, autor=yo)
    if form.is_valid():
        foto = form.save(commit=False)
        foto.restaurante, foto.autor = restaurante, yo
        foto.save()
        messages.success(request, 'Foto publicada.')
        return redirect('detalle_foto', pk=foto.pk)
    return render(request, 'formulario.html', {
        'titulo': f'Subir foto de {restaurante.nombre}', 'form': form, 'boton': 'Subir foto', 'multipart': True,
        'volver_texto': restaurante.nombre, 'volver_url': 'detalle_restaurante', 'volver_pk': restaurante.pk})


@login_required
@require_POST
def borrar_foto(request, pk):
    foto = get_object_or_404(Foto, pk=pk)
    exigir_gestion(request, foto.autor)
    restaurante_id = foto.restaurante_id
    foto.delete()
    messages.success(request, 'Foto eliminada.')
    return redirect('detalle_restaurante', pk=restaurante_id)


#me gusta / quitar me gusta (solo POST)
@login_required
@require_POST
def like_foto(request, pk):
    foto = get_object_or_404(Foto, pk=pk)
    yo = perfil_o_403(request)
    ya_le_gusta = foto.likes.filter(pk=yo.pk).exists()
    if not ya_le_gusta:
        foto.likes.add(yo)
    elif request.POST.get('solo_like') != '1':  #el doble clic solo da me gusta, nunca lo quita
        foto.likes.remove(yo)

    #petición desde JavaScript (doble clic): se contesta con JSON en vez de redirigir
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({'liked': foto.likes.filter(pk=yo.pk).exists(), 'total': foto.likes.count()})

    #desde el feed se vuelve al feed; solo se admiten direcciones de esta misma web
    siguiente = request.POST.get('next', '')
    if siguiente and url_has_allowed_host_and_scheme(siguiente, allowed_hosts={request.get_host()}):
        return redirect(siguiente)
    return redirect('detalle_foto', pk=pk)


# Comentarios -----------------------------------------------------
#tipo es 'foto' o 'resena' (viene en la URL): un comentario va sobre una cosa u otra
@login_required
@require_POST
def comentar(request, tipo, pk):
    yo = perfil_o_403(request)
    if tipo == 'foto':
        objetivo, nombre_url = get_object_or_404(Foto, pk=pk), 'detalle_foto'
    elif tipo == 'resena':
        objetivo, nombre_url = get_object_or_404(Resena, pk=pk), 'detalle_resena'
    else:
        raise PermissionDenied
    #el comentario nace ya con autor y foto/reseña puestos: el clean() del modelo lo exige al validar
    form = ComentarioForm(request.POST, instance=Comentario(autor=yo, **{tipo: objetivo}))
    if form.is_valid():
        form.save()
    else:
        messages.error(request, 'El comentario no puede estar vacío (máximo 300 caracteres).')
    return redirect(nombre_url, pk=pk)


@login_required
@require_POST
def borrar_comentario(request, pk):
    comentario = get_object_or_404(Comentario, pk=pk)
    exigir_gestion(request, comentario.autor)
    if comentario.foto_id:
        destino = redirect('detalle_foto', pk=comentario.foto_id)
    else:
        destino = redirect('detalle_resena', pk=comentario.resena_id)
    comentario.delete()
    return destino


# Administradora --------------------------------------------------
@login_required
def editar_restaurante(request, pk):
    exigir_staff(request)
    restaurante = get_object_or_404(Restaurante, pk=pk)
    form = RestauranteForm(request.POST or None, request.FILES or None, instance=restaurante)
    if form.is_valid():
        form.save()
        messages.success(request, 'Restaurante actualizado.')
        return redirect('detalle_restaurante', pk=pk)
    return render(request, 'formulario.html', {
        'titulo': f'Editar {restaurante.nombre}', 'form': form, 'boton': 'Guardar cambios', 'multipart': True,
        'volver_texto': restaurante.nombre, 'volver_url': 'detalle_restaurante', 'volver_pk': pk})


#Panel: resumen para moderar
@login_required
def panel(request):
    exigir_staff(request)
    context = {
        'cifras': [
            ('Usuarios', Perfil.objects.count()),
            ('Restaurantes', Restaurante.objects.count()),
            ('Reseñas', Resena.objects.count()),
            ('Fotos', Foto.objects.count()),
            ('Comentarios', Comentario.objects.count()),
            ('Sin portada', Restaurante.objects.filter(foto_url__isnull=True, foto='').count()),
        ],
        'mas_activos': (Restaurante.objects.select_related('ciudad')
                        .annotate(n=Count('resenas', distinct=True) + Count('fotos', distinct=True))
                        .filter(n__gt=0).order_by('-n')[:5]),
        'ultimos_usuarios': Perfil.objects.select_related('usuario', 'ciudad').order_by('-id')[:6],
        'ultimas_resenas': Resena.objects.select_related('autor__usuario', 'restaurante')[:8],
        'ultimas_fotos': Foto.objects.select_related('autor__usuario', 'restaurante')[:8],
        'ultimos_comentarios': Comentario.objects.select_related('autor__usuario').order_by('-fecha')[:8],
    }
    return render(request, 'panel.html', context)
