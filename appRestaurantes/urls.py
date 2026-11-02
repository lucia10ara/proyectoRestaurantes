from django.urls import path
from . import views

urlpatterns = [
    #Página principal (índice)
    path('', views.index, name='index'),

    #Restaurantes
    path('restaurantes/', views.lista_restaurantes, name='lista_restaurantes'),
    path('restaurantes/<int:pk>/', views.detalle_restaurante, name='detalle_restaurante'),

    #Reseñas
    path('resenas/', views.lista_resenas, name='lista_resenas'),
    path('resenas/<int:pk>/', views.detalle_resena, name='detalle_resena'),

    #Fotos
    path('fotos/', views.lista_fotos, name='lista_fotos'),
    path('fotos/<int:pk>/', views.detalle_foto, name='detalle_foto'),

    #Ciudades
    path('ciudades/', views.lista_ciudades, name='lista_ciudades'),
    path('ciudades/<int:pk>/', views.detalle_ciudad, name='detalle_ciudad'),

    #Perfiles
    path('perfiles/', views.lista_perfiles, name='lista_perfiles'),
    path('perfiles/<int:pk>/', views.detalle_perfil, name='detalle_perfil'),
]
