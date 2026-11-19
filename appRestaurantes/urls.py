from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, views_social, views_colecciones, views_avisos, views_planes, views_historias, views_diario, views_descubre

#index y listas de listas y detalles de cada modelo 

urlpatterns = [
    #pagina principal (index)
    path('', views.index, name='index'),

    #Sesión: entrar, salir (Django exige POST para salir) y crear cuenta
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html', redirect_authenticated_user=True), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('registro/', views.registro, name='registro'),

    #explorar: rejilla de fotos con filtros (como el explorar de instagram)
    path('explorar/', views.explorar, name='explorar'),

    #mapa de restaurantes (los puntos se piden por JSON según la zona que se ve)
    path('mapa/', views.mapa, name='mapa'),
    path('mapa/datos/', views.mapa_datos, name='mapa_datos'),

    #Restaurantes----------
    #/appRestaurantes/restaurantes/ -> lista de restaurantes
    path('restaurantes/', views.lista_restaurantes, name='lista_restaurantes'),
    
    #/appRestaurantes/restaurantes/1/ -> detalle del restaurante con id=1
    path('restaurantes/<int:pk>/', views.detalle_restaurante, name='detalle_restaurante'),


    #publicar y moderar (usuarios con sesión; editar y borrar: el dueño o la administradora)
    path('publicar/', views_social.publicar, name='publicar'),
    path('restaurantes/<int:pk>/resena/nueva/', views_social.crear_resena, name='crear_resena'),
    path('restaurantes/<int:pk>/foto/nueva/', views_social.subir_foto, name='subir_foto'),
    path('resenas/<int:pk>/editar/', views_social.editar_resena, name='editar_resena'),
    path('resenas/<int:pk>/borrar/', views_social.borrar_resena, name='borrar_resena'),
    path('fotos/<int:pk>/borrar/', views_social.borrar_foto, name='borrar_foto'),
    path('fotos/<int:pk>/like/', views_social.like_foto, name='like_foto'),
    path('comentar/<str:tipo>/<int:pk>/', views_social.comentar, name='comentar'),
    path('comentarios/<int:pk>/borrar/', views_social.borrar_comentario, name='borrar_comentario'),
    path('restaurantes/<int:pk>/guardar/', views_social.guardar_restaurante, name='guardar_restaurante'),
    path('restaurantes/<int:pk>/visita/', views_social.marcar_visita, name='marcar_visita'),
    path('visitas/<int:pk>/borrar/', views_social.borrar_visita, name='borrar_visita'),

    #colecciones: listas temáticas de restaurantes (las privadas solo las ve su dueño)
    path('colecciones/nueva/', views_colecciones.crear_coleccion, name='crear_coleccion'),
    path('colecciones/<int:pk>/', views_colecciones.detalle_coleccion, name='detalle_coleccion'),
    path('colecciones/<int:pk>/editar/', views_colecciones.editar_coleccion, name='editar_coleccion'),
    path('colecciones/<int:pk>/borrar/', views_colecciones.borrar_coleccion, name='borrar_coleccion'),
    path('colecciones/<int:pk>/quitar/<int:restaurante_pk>/', views_colecciones.quitar_de_coleccion, name='quitar_de_coleccion'),
    path('colecciones/<int:pk>/nota/<int:restaurante_pk>/', views_colecciones.nota_en_coleccion, name='nota_en_coleccion'),
    path('restaurantes/<int:pk>/coleccion/', views_colecciones.anadir_a_coleccion, name='anadir_a_coleccion'),
    path('perfiles/<int:pk>/colecciones/', views_colecciones.colecciones_de_perfil, name='colecciones_de_perfil'),

    #planes entre amigos (solo los ven quien los crea y los invitados)
    path('planes/', views_planes.mis_planes, name='mis_planes'),
    path('planes/<int:pk>/', views_planes.detalle_plan, name='detalle_plan'),
    path('planes/<int:pk>/responder/', views_planes.responder_plan, name='responder_plan'),
    path('planes/<int:pk>/cancelar/', views_planes.cancelar_plan, name='cancelar_plan'),
    path('restaurantes/<int:pk>/plan/nuevo/', views_planes.crear_plan, name='crear_plan'),

    #historias de 24 horas (las ven el autor y sus seguidores)
    path('restaurantes/<int:pk>/historia/nueva/', views_historias.crear_historia, name='crear_historia'),
    path('historias/<int:pk>/', views_historias.ver_historias, name='ver_historias'),  #pk = el autor
    path('historias/<int:pk>/borrar/', views_historias.borrar_historia, name='borrar_historia'),  #pk = la historia

    #descubrir: recomendaciones, novedades, joyas ocultas y ruleta
    path('descubre/', views_descubre.descubre, name='descubre'),
    path('descubre/para-ti/', views_descubre.para_ti, name='para_ti'),
    path('descubre/novedades/', views_descubre.novedades, name='novedades'),
    path('descubre/joyas/', views_descubre.joyas, name='joyas'),
    path('descubre/ruleta/', views_descubre.ruleta, name='ruleta'),

    #mi diario, pasaporte de sellos y retos (personales: salen de las visitas confirmadas)
    path('diario/', views_diario.diario, name='diario'),
    path('diario/pasaporte/', views_diario.pasaporte, name='pasaporte'),
    path('diario/retos/', views_diario.mis_retos, name='mis_retos'),

    #avisos (notificaciones) del usuario
    path('avisos/', views_avisos.avisos, name='avisos'),
    path('avisos/borrar-leidos/', views_avisos.avisos_borrar_leidos, name='avisos_borrar_leidos'),

    #solo administradora
    path('panel/', views_social.panel, name='panel'),
    path('restaurantes/<int:pk>/editar/', views_social.editar_restaurante, name='editar_restaurante'),

    #Reseñas-----------
    path('resenas/', views.lista_resenas, name='lista_resenas'),
    path('resenas/<int:pk>/', views.detalle_resena, name='detalle_resena'),

    #Fotos----------------
    path('fotos/', views.lista_fotos, name='lista_fotos'),
    path('fotos/<int:pk>/', views.detalle_foto, name='detalle_foto'),

    #Ciudades------------
    path('ciudades/', views.lista_ciudades, name='lista_ciudades'),
    path('ciudades/por-comunidad/', views.ciudades_comunidad, name='ciudades_comunidad'),  #JSON con las ciudades de una comunidad
    path('ciudades/<int:pk>/', views.detalle_ciudad, name='detalle_ciudad'),

    #Perfiles------------------
    path('perfiles/', views.lista_perfiles, name='lista_perfiles'),
    path('perfiles/<int:pk>/', views.detalle_perfil, name='detalle_perfil'),
    path('perfiles/<int:pk>/seguir/', views.seguir, name='seguir'),  #seguir / dejar de seguir (solo POST)
]
