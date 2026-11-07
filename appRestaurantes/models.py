from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

#Siempre que modifico este archivo hago python manage.py makemigrations y python manage.py migrate
#Nota: hemos cargado algunos datos de prueba con un json creado por la IA, a partir de ahí hemos subido algunas cosas nuestras desde admin

class Ciudad(models.Model):
    nombre = models.CharField(max_length=100, unique=True)  #nombre de la ciudad, no se puede repetir
    comunidad = models.CharField(max_length=100, blank=True, null=True)  #comunidad autonoma a la que pertenece

    class Meta: #nombres en singular y plural
        verbose_name = "Ciudad"
        verbose_name_plural = "Ciudades"
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Perfil(models.Model):
    usuario = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')  #usuario de Django, cada uno tiene un perfil (relación uno a uno)
    
    foto_url = models.URLField(max_length=300, blank=True, null=True)  #foto de perfil (enlace)
    foto = models.ImageField(upload_to='perfiles/', blank=True, null=True)  #foto de perfil subida desde el ordenador (alternativa al enlace)
    
    biografia = models.CharField(max_length=250, blank=True, null=True)  #texto corto que el usuario pone sobre sí mismo
    ciudad = models.ForeignKey(Ciudad, on_delete=models.SET_NULL, related_name='perfiles',
                               blank=True, null=True)  #ciudad donde vive, si se borra la ciudad el perfil se queda sin ciudad
    
    fecha_alta = models.DateField(auto_now_add=True)  #dia en que se registró, se pone solo
    siguiendo = models.ManyToManyField('self', blank=True, symmetrical=False, related_name='seguidores')  #gente a la que sigo, no tiene por qué seguirme de vuelta

    class Meta:  
        verbose_name = "Perfil"
        verbose_name_plural = "Perfiles"
        ordering = ['usuario__username']

    def __str__(self):
        return self.usuario.username

    #definimos esto para elegir que es lo que se enseña en la plantilla: la imagen subida si hay, si no el enlace
    @property
    def imagen_src(self):
        if self.foto:
            return self.foto.url
        return self.foto_url

    @property
    def amigos(self):
        #amigos = seguimiento mutuo (yo sigo a esa persona y ella me sigue a mi) --> se calcula
        return self.siguiendo.filter(siguiendo=self)


class Alergeno(models.Model):
    nombre = models.CharField(max_length=50, unique=True)  #gluten, lactosa..

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
    
    descripcion = models.TextField(blank=True, null=True) 
    
    foto_url = models.URLField(max_length=300, blank=True, null=True)  #foto de portada del restaurante (enlace)
    foto = models.ImageField(upload_to='restaurantes/', blank=True, null=True)  #portada subida desde el ordenador (alternativa al enlace)
    
    admite_ninos = models.BooleanField('Admite niños', default=True)  #si se puede ir con niños (el primer argumento es el nombre que se ve en el admin, el campo se llama sin ñ)
    admite_perros = models.BooleanField(default=False)  #si se puede ir con perro
    opciones_sin_alergenos = models.ManyToManyField(Alergeno, blank=True, related_name='restaurantes')  #alergenos para los que tiene opciones adaptadas (relación muchos a muchos)


    class Meta:
        verbose_name = "Restaurante"
        verbose_name_plural = "Restaurantes"
        ordering = ['nombre']
        #definimos constraints para hacer el restaurante único por ciudad, nomber y direccion
        constraints = [  #mismo nombre y misma ciudad sí, pero no en la misma dirección
            models.UniqueConstraint(fields=['ciudad', 'nombre', 'direccion'], name='restaurante_unico_por_local'),
        ]

    def __str__(self):
        return self.nombre

    
    @property
    def imagen_src(self):
        if self.foto:
            return self.foto.url
        return self.foto_url


class Resena(models.Model):
    restaurante = models.ForeignKey(Restaurante, on_delete=models.CASCADE, related_name='resenas')  #restaurante del que es la reseña
    autor = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='resenas')  #perfil que la escribe
    
    puntuacion = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])  #estrellas de 1 a 5
    titulo = models.CharField(max_length=100)  #titulo de la reseña
    texto = models.TextField()  #la opinion
    fecha = models.DateField(auto_now_add=True) 

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
    
    url = models.URLField(max_length=300, blank=True, null=True)  #enlace a la imagen (opcional si se sube un archivo)
    imagen = models.ImageField(upload_to='fotos/', blank=True, null=True)  #imagen subida desde el ordenador (opcional si hay enlace)
    pie = models.CharField(max_length=200, blank=True, null=True)
    fecha = models.DateField(auto_now_add=True)  #dia en que se subió, se pone solo

    class Meta:
        verbose_name = "Foto"
        verbose_name_plural = "Fotos"
        ordering = ['-fecha', '-id']

    def __str__(self):
        return f"Foto de {self.restaurante.nombre} por {self.autor}"

    def clean(self):
        #tiene que haber al menos una de las dos: archivo o enlace
        if not self.imagen and not self.url:
            raise ValidationError("Sube una imagen o pon un enlace a la imagen.")

    @property
    def imagen_src(self):
        if self.imagen:
            return self.imagen.url
        return self.url


class Comentario(models.Model):
    #un comentario va sobre una foto o sobre una reseña, nunca las dos
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
        #solo uno de los dos: foto o reseña --> sino error
        if bool(self.foto) == bool(self.resena):
            raise ValidationError("El comentario debe ir sobre una foto o sobre una reseña (solo una).")

    def __str__(self):
        return f"{self.autor}: {self.texto[:30]}"
