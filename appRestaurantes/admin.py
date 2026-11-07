from django.contrib import admin
from .models import Perfil, Ciudad, Alergeno, Restaurante, Resena, Foto, Comentario

#Definimos los modelos en el admin para poder registrar instancias
admin.site.register(Perfil)

admin.site.register(Ciudad)

admin.site.register(Alergeno) #registro simple

admin.site.register(Restaurante)

#Fotos dentro de la reseña: se añaden varias desde la propia página de la reseña
class FotoInline(admin.TabularInline):
    model = Foto
    extra = 2  #filas vacías para añadir fotos
    fields = ('tipo', 'imagen', 'url', 'pie')  #restaurante y autor se rellenan solos con los de la reseña


@admin.register(Resena)
class ResenaAdmin(admin.ModelAdmin):
    inlines = [FotoInline]

    def save_formset(self, request, form, formset, change):
        fotos = formset.save(commit=False)
        for foto in fotos:
            foto.restaurante = form.instance.restaurante  #la foto es del mismo restaurante que la reseña
            foto.autor = form.instance.autor  #y la sube el autor de la reseña
            foto.save()
        formset.save_m2m()

admin.site.register(Foto)

admin.site.register(Comentario)
