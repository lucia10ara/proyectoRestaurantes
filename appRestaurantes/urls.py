from django.urls import path
from django.contrib.auth import views as auth_views
from . import views, views_social

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
