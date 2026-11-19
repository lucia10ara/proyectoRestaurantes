import unicodedata

from django.contrib.auth.models import User
from django.templatetags.static import static
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models

#!! python manage.py makemigrations y python manage.py migrate

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
    lleva_ninos = models.BooleanField('Suelo ir con niños', default=False)  #preferencia del usuario: ya estaba en la base de datos (migración 0006)
    lleva_perros = models.BooleanField('Suelo ir con perro', default=False)  #preferencia del usuario: ya estaba en la base de datos (migración 0006)

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

    #ubicación (de OpenStreetMap). Vacía si todavía no la conocemos: el mapa solo enseña los que la tienen
    latitud = models.FloatField(blank=True, null=True)
    longitud = models.FloatField(blank=True, null=True)

    #fecha en la que el restaurante se AÑADIÓ A LA APP (no es la fecha de apertura del local, que no la conocemos).
    #Los importados antes de existir este campo la tienen vacía
    fecha_alta = models.DateTimeField('Añadido a la app', auto_now_add=True, null=True)

    #datos que se van completando poco a poco (OpenStreetMap, la administradora...).
    #None significa "no lo sabemos": nunca se enseña como confirmado
    PRECIOS = [(1, 'Económico'), (2, 'Medio'), (3, 'Caro')]
    precio = models.PositiveSmallIntegerField('Precio aproximado', choices=PRECIOS, blank=True, null=True)
    precio_max_persona = models.PositiveSmallIntegerField('Precio máximo por persona (€)', blank=True, null=True)
    terraza = models.BooleanField('Terraza', blank=True, null=True)
    menu_del_dia = models.BooleanField('Menú del día', blank=True, null=True)
    vegetariano = models.BooleanField('Opciones vegetarianas', blank=True, null=True)
    vegano = models.BooleanField('Opciones veganas', blank=True, null=True)
    para_grupos = models.BooleanField('Apto para grupos', blank=True, null=True)
    accesible = models.BooleanField('Accesible', blank=True, null=True)
    momentos = models.ManyToManyField('MomentoComida', blank=True, related_name='restaurantes', verbose_name='Tipo de comida')

    class Meta:
        verbose_name = "Restaurante"
        verbose_name_plural = "Restaurantes"
        ordering = ['nombre']
        #definimos constraints para hacer el restaurante único por ciudad, nomber y direccion
        constraints = [  #mismo nombre y misma ciudad sí, pero no en la misma dirección
            models.UniqueConstraint(fields=['ciudad', 'nombre', 'direccion'], name='restaurante_unico_por_local'),
        ]
        indexes = [  #el mapa busca por zona (latitud/longitud) y novedades por fecha de alta
            models.Index(fields=['latitud', 'longitud'], name='resto_coordenadas'),
            models.Index(fields=['fecha_alta'], name='resto_fecha_alta'),
            models.Index(fields=['tipo_cocina'], name='resto_tipo_cocina'),
        ]

    def __str__(self):
        return self.nombre

    
    #imagen del restaurante en 3 niveles, se usa el primero que exista:
    #  1) la portada puesta por la administradora (archivo o enlace; también los enlaces de OpenStreetMap)
    #  2) la foto con más me gusta que hayan subido los usuarios a este restaurante
    #  3) una ilustración según el tipo de cocina
    @property
    def direccion_visible(self):  #los importados sin calle guardan las coordenadas como dirección: eso no se enseña
        return '' if self.direccion.startswith('Coordenadas') else self.direccion

    @property
    def imagen_real(self):  #solo fotos de verdad (niveles 1 y 2), None si no hay
        if self.foto:
            return self.foto.url
        if self.foto_url:
            return self.foto_url
        mejor = self.fotos.annotate(n=models.Count('likes')).order_by('-n', '-id').first()
        return mejor.imagen_src if mejor else None

    @property
    def imagen_generica(self):  #ilustración según la cocina (nivel 3)
        return static(f'img/cocinas/{categoria_cocina(self.tipo_cocina)}.svg')

    @property
    def imagen_src(self):  #la que usan las tarjetas: foto real si hay, y si no la ilustración
        return self.imagen_real or self.imagen_generica


#categoría de ilustración según el tipo de cocina (se busca la palabra clave, sin tildes ni mayúsculas)
CATEGORIAS_COCINA = [
    ('pizza', ('pizz',)),
    ('sushi', ('japon', 'sushi', 'ramen', 'corean')),
    ('pasta', ('italian', 'pasta')),
    ('hamburguesa', ('hamburg', 'american', 'burger')),
    ('asiatica', ('chin', 'asiat', 'thai', 'vietnam')),
    ('mexicana', ('mexic', 'argentin', 'peruan', 'brasil')),
    ('kebab', ('kebab', 'turco', 'arabe', 'libanes', 'marroqu', 'indio')),
    ('marisco', ('marisq', 'marisc', 'pescado', 'fish')),
    ('carne', ('asador', 'parrilla', 'pollo', 'carne', 'steak')),
    ('arroz', ('arroc',)),
    ('vegetariano', ('vegetar', 'vegan')),
    ('bocadillo', ('bocadill', 'sandwich')),
    ('cafe', ('cafeter', 'coffee')),
    ('tapas', ('tapas', 'pintxo', 'sidrer', 'cider', 'vasco', 'basque', 'regional', 'espan', 'mediterr')),
]

def categoria_cocina(tipo):
    texto = unicodedata.normalize('NFD', (tipo or '').lower())
    texto = ''.join(c for c in texto if unicodedata.category(c) != 'Mn')  #quitamos las tildes
    for categoria, claves in CATEGORIAS_COCINA:
        if any(clave in texto for clave in claves):
            return categoria
    return 'generica'


class MomentoComida(models.Model):
    #desayuno, brunch, comida, cena, merienda (tabla pequeña para poder filtrar por varios a la vez)
    clave = models.SlugField(max_length=20, unique=True)
    nombre = models.CharField(max_length=30)
    orden = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name = "Tipo de comida"
        verbose_name_plural = "Tipos de comida"
        ordering = ['orden']

    def __str__(self):
        return self.nombre


class Guardado(models.Model):
    #restaurante que un usuario quiere visitar ("pendiente"). Guardar NO es haber ido
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='guardados')
    restaurante = models.ForeignKey(Restaurante, on_delete=models.CASCADE, related_name='guardados')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Restaurante guardado"
        verbose_name_plural = "Restaurantes guardados"
        ordering = ['-fecha']
        constraints = [models.UniqueConstraint(fields=['perfil', 'restaurante'], name='guardado_unico')]

    def __str__(self):
        return f"{self.perfil} guardó {self.restaurante}"


class Visita(models.Model):
    #VISITA CONFIRMADA: solo la crea el propio usuario (botón "He estado aquí" o la casilla "Estuve aquí" al reseñar).
    #Es lo único que cuenta para el diario, el pasaporte, los retos y "amigos que han estado"
    ORIGENES = [('boton', 'He estado aquí'), ('resena', 'Al escribir una reseña')]
    perfil = models.ForeignKey(Perfil, on_delete=models.CASCADE, related_name='visitas')
    restaurante = models.ForeignKey(Restaurante, on_delete=models.CASCADE, related_name='visitas')
    fecha = models.DateField('Día de la visita')
    origen = models.CharField(max_length=10, choices=ORIGENES, default='boton')
    creada = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Visita confirmada"
        verbose_name_plural = "Visitas confirmadas"
        ordering = ['-fecha', '-creada']
        #una visita por persona, restaurante y día (evita sumar visitas repetidas el mismo día)
        constraints = [models.UniqueConstraint(fields=['perfil', 'restaurante', 'fecha'], name='visita_unica_por_dia')]
        indexes = [models.Index(fields=['perfil', 'fecha'], name='visita_perfil_fecha')]

    def __str__(self):
        return f"{self.perfil} en {self.restaurante} ({self.fecha})"


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
