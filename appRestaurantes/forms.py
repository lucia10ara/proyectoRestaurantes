from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from .models import Ciudad, Perfil, Resena, Foto, Comentario, Restaurante, Coleccion, Historia


#Formulario de registro: el de Django (usuario + contraseña dos veces) más la ciudad y la biografía, que van en el Perfil
class RegistroForm(UserCreationForm):
    #la ciudad se elige en dos pasos: primero la comunidad (solo sirve para rellenar las ciudades, no se guarda) y luego la ciudad
    comunidad = forms.ChoiceField(required=False, label='Comunidad autónoma')
    ciudad = forms.ModelChoiceField(queryset=Ciudad.objects.all(), required=False,
                                    empty_label='— Primero elige tu comunidad —',
                                    help_text='La usaremos para enseñarte primero los sitios de tu ciudad en Explorar.')
    biografia = forms.CharField(max_length=250, required=False, label='Biografía',
                                help_text='Opcional: una frase sobre ti.')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        comunidades = (Ciudad.objects.exclude(comunidad__isnull=True).exclude(comunidad='')
                       .order_by('comunidad').values_list('comunidad', flat=True).distinct())
        self.fields['comunidad'].choices = [('', '— Elige tu comunidad —')] + [(c, c) for c in comunidades]

        #el desplegable de ciudades empieza vacío (la validación sigue usando todas); la web lo rellena al elegir comunidad
        #(static/js/ciudades.js). Si el formulario vuelve con errores, lo dejamos relleno con las ciudades de la comunidad elegida
        comunidad = self.data.get('comunidad') if self.is_bound else None
        opciones = [('', '— Primero elige tu comunidad —')]
        if comunidad:
            ciudades = (Ciudad.objects.filter(comunidad=comunidad, restaurantes__isnull=False)
                        .distinct().order_by('nombre'))
            opciones = [('', '— Elige tu ciudad —')] + [(c.id, c.nombre) for c in ciudades]
        self.fields['ciudad'].widget.choices = opciones
        self.fields['ciudad'].widget.attrs['data-vacio'] = '— Elige tu ciudad —'
        self.fields['comunidad'].widget.attrs['data-ciudades'] = 'id_ciudad'
        self.fields['comunidad'].widget.attrs['data-url'] = reverse('ciudades_comunidad')

    def save(self, commit=True):
        usuario = super().save(commit=commit)
        if commit:
            #cada usuario tiene su perfil (relación uno a uno), lo creamos a la vez
            Perfil.objects.create(usuario=usuario,
                                  ciudad=self.cleaned_data['ciudad'],
                                  biografia=self.cleaned_data['biografia'] or None)
        return usuario


#Reseña: el autor y el restaurante los pone la vista (son el usuario que ha entrado y el restaurante de la página)
ESTRELLAS = [(5, '★★★★★  Excelente'), (4, '★★★★  Muy bueno'), (3, '★★★  Normal'), (2, '★★  Flojo'), (1, '★  Malo')]


class ResenaForm(forms.ModelForm):
    puntuacion = forms.TypedChoiceField(label='Nota general', coerce=int, choices=ESTRELLAS)
    #notas por categoría: obligatorias en las reseñas nuevas, opcionales al editar una antigua que no las tenía
    nota_comida = forms.TypedChoiceField(label='Comida', coerce=int, empty_value=None, choices=[('', '—')] + ESTRELLAS)
    nota_servicio = forms.TypedChoiceField(label='Servicio', coerce=int, empty_value=None, choices=[('', '—')] + ESTRELLAS)
    nota_ambiente = forms.TypedChoiceField(label='Ambiente', coerce=int, empty_value=None, choices=[('', '—')] + ESTRELLAS)
    nota_calidad_precio = forms.TypedChoiceField(label='Calidad-precio', coerce=int, empty_value=None, choices=[('', '—')] + ESTRELLAS)
    titulo = forms.CharField(max_length=100, label='Título', widget=forms.TextInput(attrs={'placeholder': 'Resume tu experiencia'}))
    texto = forms.CharField(label='Tu opinión', widget=forms.Textarea(attrs={'rows': 5, 'placeholder': '¿Qué tal la comida, el servicio, el ambiente?'}))
    #solo al crear: si marca que estuvo, se apunta una visita confirmada en su diario
    estuve = forms.BooleanField(label='Estuve aquí (apuntar la visita en mi diario)', required=False, initial=True)
    fecha_visita = forms.DateField(label='Día de la visita', required=False, widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))

    class Meta:
        model = Resena
        fields = ('puntuacion', 'nota_comida', 'nota_servicio', 'nota_ambiente', 'nota_calidad_precio', 'titulo', 'texto')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nueva = self.instance.pk is None
        for campo, _ in Resena.CATEGORIAS:
            self.fields[campo].required = nueva
        if nueva:
            self.fields['fecha_visita'].initial = date.today()
            self.fields['fecha_visita'].widget.attrs['max'] = date.today().isoformat()
        else:  #al editar no se crean visitas (ya están en el diario o se apuntan con el botón)
            del self.fields['estuve']
            del self.fields['fecha_visita']

    def clean(self):
        datos = super().clean()
        if datos.get('estuve'):
            fecha = datos.get('fecha_visita') or date.today()
            if fecha > date.today():
                self.add_error('fecha_visita', 'La visita no puede ser en el futuro.')
            datos['fecha_visita'] = fecha
        return datos


MAX_MB_HISTORIA = 5  #tamaño máximo de las imágenes subidas (fotos e historias)


#Foto: archivo subido o enlace (hace falta uno de los dos, lo comprueba el clean del modelo); la reseña es opcional
class FotoForm(forms.ModelForm):
    class Meta:
        model = Foto
        fields = ('tipo', 'imagen', 'url', 'pie', 'resena')
        labels = {'imagen': 'Imagen (archivo)', 'url': 'o enlace a la imagen', 'pie': 'Pie de foto', 'resena': 'Asociarla a una de mis reseñas'}

    def __init__(self, *args, restaurante=None, autor=None, **kwargs):
        super().__init__(*args, **kwargs)
        #solo puede asociarla a reseñas suyas de este restaurante
        reseñas = Resena.objects.filter(restaurante=restaurante, autor=autor) if restaurante and autor else Resena.objects.none()
        self.fields['resena'].queryset = reseñas
        self.fields['resena'].empty_label = '— Ninguna —'

    def clean_imagen(self):
        imagen = self.cleaned_data.get('imagen')
        if imagen and imagen.size > MAX_MB_HISTORIA * 1024 * 1024:  #el mismo límite que las historias: 5 MB
            raise forms.ValidationError(f'La imagen pesa demasiado (máximo {MAX_MB_HISTORIA} MB).')
        return imagen


class ComentarioForm(forms.ModelForm):
    class Meta:
        model = Comentario
        fields = ('texto',)


#Edición de un restaurante (solo la administradora): para poner foto, descripción y corregir los datos importados.
#Los sí/no nuevos tienen tres opciones (desconocido, sí, no): lo que no se sabe no se enseña como confirmado
class RestauranteForm(forms.ModelForm):
    class Meta:
        model = Restaurante
        fields = ('nombre', 'tipo_cocina', 'direccion', 'descripcion', 'foto', 'foto_url',
                  'latitud', 'longitud', 'precio', 'precio_max_persona', 'momentos',
                  'terraza', 'menu_del_dia', 'vegetariano', 'vegano', 'para_grupos', 'accesible',
                  'admite_ninos', 'admite_perros', 'opciones_sin_alergenos')
        labels = {'foto': 'Portada (archivo)', 'foto_url': 'o enlace a la portada'}
        widgets = {'opciones_sin_alergenos': forms.CheckboxSelectMultiple, 'momentos': forms.CheckboxSelectMultiple,
                   'descripcion': forms.Textarea(attrs={'rows': 4})}

    def clean(self):
        datos = super().clean()
        lat, lon = datos.get('latitud'), datos.get('longitud')
        if (lat is None) != (lon is None):
            raise forms.ValidationError('Pon latitud y longitud a la vez, o deja las dos vacías.')
        if lat is not None and not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise forms.ValidationError('Esas coordenadas no son válidas.')
        return datos


#Colección: el dueño lo pone la vista. El nombre no se puede repetir entre las colecciones del mismo usuario
class ColeccionForm(forms.ModelForm):
    class Meta:
        model = Coleccion
        fields = ('nombre', 'descripcion', 'publica')
        labels = {'nombre': 'Nombre', 'descripcion': 'Descripción (opcional)'}
        widgets = {'nombre': forms.TextInput(attrs={'placeholder': 'Para cumpleaños, cenas románticas…'})}

    def __init__(self, *args, perfil=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.perfil = perfil

    def clean_nombre(self):
        nombre = self.cleaned_data['nombre'].strip()
        repetidas = Coleccion.objects.filter(perfil=self.perfil, nombre__iexact=nombre).exclude(pk=self.instance.pk)
        if repetidas.exists():
            raise forms.ValidationError('Ya tienes una colección con ese nombre.')
        return nombre


#Historia de 24 horas: imagen (archivo o enlace) y un texto corto; el autor y el restaurante los pone la vista
class HistoriaForm(forms.ModelForm):
    class Meta:
        model = Historia
        fields = ('imagen', 'url', 'texto')
        labels = {'imagen': 'Imagen (archivo)', 'texto': 'Texto (opcional)'}
        widgets = {'texto': forms.TextInput(attrs={'placeholder': 'Lo que quieras contar (máximo 140 letras)'})}

    def clean_imagen(self):
        imagen = self.cleaned_data.get('imagen')
        if imagen and imagen.size > MAX_MB_HISTORIA * 1024 * 1024:
            raise forms.ValidationError(f'La imagen pesa demasiado (máximo {MAX_MB_HISTORIA} MB).')
        return imagen


#Plan: quedada con amigos (seguimiento mutuo). Solo se puede invitar a amigos y la fecha tiene que ser futura
MAX_INVITADOS = 20


class PlanForm(forms.Form):
    cuando = forms.DateTimeField(label='Día y hora', input_formats=['%Y-%m-%dT%H:%M'],
                                 widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'))
    mensaje = forms.CharField(label='Mensaje (opcional)', max_length=200, required=False,
                              widget=forms.TextInput(attrs={'placeholder': '¡Vamos a probar el menú del día!'}))
    invitados = forms.ModelMultipleChoiceField(label='¿A quién invitas?', queryset=Perfil.objects.none(),
                                               widget=forms.CheckboxSelectMultiple,
                                               help_text='Solo puedes invitar a tus amigos (gente a la que sigues y que te sigue).')

    def __init__(self, *args, amigos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['invitados'].queryset = amigos if amigos is not None else Perfil.objects.none()

    def clean_cuando(self):
        cuando = self.cleaned_data['cuando']
        if cuando <= timezone.now():
            raise forms.ValidationError('El plan tiene que ser en el futuro.')
        return cuando

    def clean_invitados(self):
        invitados = self.cleaned_data['invitados']
        if len(invitados) > MAX_INVITADOS:
            raise forms.ValidationError(f'Máximo {MAX_INVITADOS} invitados.')
        return invitados


#Editar un plan: solo se cambian el día y hora y el mensaje (los invitados no se tocan)
class PlanEditarForm(PlanForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        del self.fields['invitados']


#Visita confirmada: el usuario dice qué día estuvo (no puede ser en el futuro)
class VisitaForm(forms.Form):
    fecha = forms.DateField(label='¿Qué día fuiste?', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        hoy = date.today()
        if fecha > hoy:
            raise forms.ValidationError('La visita no puede ser en el futuro.')
        if fecha.year < 1950:
            raise forms.ValidationError('Esa fecha no parece correcta.')
        return fecha
