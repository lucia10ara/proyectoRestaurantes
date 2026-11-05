from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

#Siempre que modifico este archivo hago python manage.py makemigrations y python manage.py migrate


class Ciudad(models.Model):
    nombre = models.CharField(max_length=100, unique=True)  #nombre de la ciudad, no se puede repetir
    comunidad = models.CharField(max_length=100, blank=True, null=True)  #comunidad autónoma a la que pertenece

    class Meta:
        verbose_name = "Ciudad"
        verbose_name_plural = "Ciudades"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')  #usuario de Django, cada uno tiene un perfil (relación uno a uno)
    foto_url = models.URLField(max_length=300, blank=True, null=True)  #foto de perfil
    biografia = models.CharField(max_length=250, blank=True, null=True)  #texto corto que el usuario pone sobre sí mismo
    ciudad = models.ForeignKey(Ciudad, on_delete=models.SET_NULL, related_name='perfiles',
                               blank=True, null=True)  #ciudad donde vive, si se borra la ciudad el perfil se queda sin ciudad
    fecha_alta = models.DateField(auto_now_add=True)  #día en que se registró, se pone solo
    amigos = models.ManyToManyField('self', blank=True)  #amigos, si yo soy tu amiga tú eres la mía (relación simétrica)
    siguiendo = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='seguidores')  #gente a la que sigo, no tiene por qué seguirme de vuelta

    class Meta:  #Nombres en singular y plural para el panel de administración
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"
        ordering = ['usuario__username']

    def __str__(self):
        return self.usuario.username


class Alergeno(models.Model):
    nombre = models.CharField(max_length=50, unique=True)  #nombre del alérgeno (gluten, lactosa...)

    class Meta:
        verbose_name = "Alérgeno"
        verbose_name_plural = "Alérgenos"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Restaurante(models.Model):
    ciudad = models.ForeignKey(Ciudad, on_delete=models.CASCADE, related_name='restaurantes')  #ciudad donde está, una ciudad tiene muchos restaurantes (relación uno a muchos)
    nombre = models.CharField(max_length=100)  #nombre del restaurante, puede repetirse (cadenas con varios locales)
    tipo_cocina = models.CharField(max_length=50)  #tipo de comida (pintxos, italiano, asador...)
    direccion = models.CharField(max_length=200)  #calle y número, obligatoria para distinguir locales de una misma cadena
    descripcion = models.TextField(blank=True, null=True)  #descripción larga del sitio
    admite_ninos = models.BooleanField(default=True)  #si se puede ir con niños
    admite_perros = models.BooleanField(default=False)  #si se puede ir con perro
    opciones_sin_alergenos = models.ManyToManyField(Alergeno, blank=True, related_name='restaurantes')  #alérgenos para los que tiene opciones adaptadas (relación muchos a muchos)


    class Meta:
        verbose_name = "Restaurante"
        verbose_name_plural = "Restaurantes"
        ordering = ['nombre']
        constraints = [  #mismo nombre y misma ciudad sí, pero no en la misma dirección
            models.UniqueConstraint(fields=['ciudad', 'nombre', 'direccion'], name='restaurante_unico_por_local'),
        ]

    def __str__(self):
        return self.nombre


class Resena(models.Model):
    restaurante = models.ForeignKey(Restaurante, on_delete=models.CASCADE, related_name='resenas')  #restaurante del que es la reseña
    autor = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='resenas')  #perfil que la escribe
    puntuacion = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])  #estrellas de 1 a 5
    titulo = models.CharField(max_length=100)  #título de la reseña
    texto = models.TextField()  #la opinión en sí
    fecha = models.DateField(auto_now_add=True)  #día en que se publicó, se pone solo

    class Meta:
        verbose_name = "Reseña"
        verbose_name_plural = "Reseñas"
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"{self.titulo} - {self.autor} ({self.puntuacion}★)"


class Foto(models.Model):
    restaurante = models.ForeignKey(Restaurante, on_delete=models.CASCADE, related_name='fotos')  #restaurante de la foto
    autor = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='fotos')  #perfil que la sube
    resena = models.ForeignKey(Resena, on_delete=models.SET_NULL, related_name='fotos',
                               blank=True, null=True)  #reseña a la que va asociada, es opcional
    likes = models.ManyToManyField(Perfil, related_name='fotos_gustadas', blank=True)  #perfiles que le han dado me gusta (relación muchos a muchos)
    
    TIPOS = [ #definimos los tipos de foto que hay para subir, para luego poder clasificarlos
        ('comida', 'Comida'),
        ('local', 'Local'),
        ('amigos', 'Amigos'),
    ]
    tipo = models.CharField(max_length=10, choices=TIPOS, default='comida')  #en choices ponemos de qué es la foto
    url = models.URLField(max_length=300)  #enlace a la imagen
    pie = models.CharField(max_length=200, blank=True, null=True)  #texto que va debajo de la foto
    fecha = models.DateField(auto_now_add=True)  #día en que se subió, se pone solo

    class Meta:
        verbose_name = "Foto"
        verbose_name_plural = "Fotos"
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"Foto de {self.restaurante.nombre} por {self.autor}"


class Comentario(models.Model):
    #Un comentario va sobre una foto O sobre una reseña, nunca las dos
    autor = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='comentarios')  #perfil que comenta
    foto = models.ForeignKey(Foto, on_delete=models.CASCADE, related_name='comentarios',
                             blank=True, null=True)  #foto comentada (si va sobre una foto)
    resena = models.ForeignKey(Resena, on_delete=models.CASCADE, related_name='comentarios',
                               blank=True, null=True)  #reseña comentada (si va sobre una reseña)
    texto = models.CharField(max_length=300)  #lo que pone el comentario
    fecha = models.DateTimeField(auto_now_add=True)  #día y hora del comentario, se pone solo

    class Meta:
        verbose_name = "Comentario"
        verbose_name_plural = "Comentarios"
        ordering = ['fecha']

    def clean(self):
        #Exactamente uno de los dos: foto o reseña
        if bool(self.foto) == bool(self.resena):
            raise ValidationError("El comentario debe ir sobre una foto o sobre una reseña (solo una).")

    def __str__(self):
        return f"{self.autor}: {self.texto[:30]}"
