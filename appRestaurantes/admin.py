from django.contrib import admin
from .models import Perfil, Ciudad, Alergeno, Restaurante, Resena, Foto, Comentario, MomentoComida, Guardado, Visita, Coleccion, ElementoColeccion, Notificacion, Plan, Invitacion

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

admin.site.register(MomentoComida)


@admin.register(Guardado)
class GuardadoAdmin(admin.ModelAdmin):
    list_display = ('perfil', 'restaurante', 'fecha')
    raw_id_fields = ('restaurante',)  #con 62.000 restaurantes un desplegable sería inmanejable


class ElementoInline(admin.TabularInline):
    model = ElementoColeccion
    extra = 0
    raw_id_fields = ('restaurante',)


@admin.register(Coleccion)
class ColeccionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'perfil', 'publica', 'creada')
    list_filter = ('publica',)
    inlines = [ElementoInline]


@admin.register(Visita)
class VisitaAdmin(admin.ModelAdmin):
    list_display = ('perfil', 'restaurante', 'fecha', 'origen')
    list_filter = ('origen',)
    raw_id_fields = ('restaurante',)


@admin.register(Notificacion)
class NotificacionAdmin(admin.ModelAdmin):
    list_display = ('destinatario', 'tipo', 'texto', 'leida', 'creada')
    list_filter = ('tipo', 'leida')


class InvitacionInline(admin.TabularInline):
    model = Invitacion
    extra = 0


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ('creador', 'restaurante', 'cuando', 'cancelado')
    list_filter = ('cancelado',)
    raw_id_fields = ('restaurante',)
    inlines = [InvitacionInline]
