from django.contrib import admin
from .models import Perfil, Ciudad, Alergeno, Restaurante, Resena, Foto, Comentario


@admin.register(Perfil)
class PerfilAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'ciudad', 'fecha_alta')
    search_fields = ('usuario__username',)


@admin.register(Ciudad)
class CiudadAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'comunidad')


admin.site.register(Alergeno)


@admin.register(Restaurante)
class RestauranteAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ciudad', 'tipo_cocina', 'admite_ninos', 'admite_perros')
    list_filter = ('ciudad', 'admite_ninos', 'admite_perros', 'opciones_sin_alergenos')
    search_fields = ('nombre', 'direccion')


@admin.register(Resena)
class ResenaAdmin(admin.ModelAdmin):
    list_display = ('titulo', 'restaurante', 'autor', 'puntuacion', 'fecha')
    list_filter = ('puntuacion', 'restaurante')


@admin.register(Foto)
class FotoAdmin(admin.ModelAdmin):
    list_display = ('restaurante', 'autor', 'tipo', 'fecha')
    list_filter = ('tipo', 'restaurante')


@admin.register(Comentario)
class ComentarioAdmin(admin.ModelAdmin):
    list_display = ('autor', 'foto', 'resena', 'texto', 'fecha')
