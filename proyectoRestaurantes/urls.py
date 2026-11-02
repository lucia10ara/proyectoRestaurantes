"""URLs principales del proyecto."""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    #Todo lo demás lo gestiona la aplicación (la página principal es el índice)
    path('', include('appRestaurantes.urls')),
]
