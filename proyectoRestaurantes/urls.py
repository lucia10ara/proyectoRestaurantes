"""URLs principales del proyecto."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    #todo lo demás lo gestiona la app (la página principal es el index)
    path('', include('appRestaurantes.urls')),
]

#en desarrollo - sirve las imágenes subidas desde la carpeta media
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
