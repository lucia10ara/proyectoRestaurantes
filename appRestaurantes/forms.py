from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.urls import reverse

from .models import Ciudad, Perfil, Resena, Foto, Comentario, Restaurante


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
class ResenaForm(forms.ModelForm):
    puntuacion = forms.TypedChoiceField(
        label='Puntuación', coerce=int,
        choices=[(5, '★★★★★  Excelente'), (4, '★★★★  Muy bueno'), (3, '★★★  Normal'), (2, '★★  Flojo'), (1, '★  Malo')])
    titulo = forms.CharField(max_length=100, label='Título', widget=forms.TextInput(attrs={'placeholder': 'Resume tu experiencia'}))
    texto = forms.CharField(label='Tu opinión', widget=forms.Textarea(attrs={'rows': 5, 'placeholder': '¿Qué tal la comida, el servicio, el ambiente?'}))

    class Meta:
        model = Resena
        fields = ('puntuacion', 'titulo', 'texto')


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


#Visita confirmada: el usuario dice qué día estuvo (no puede ser en el futuro)
class VisitaForm(forms.Form):
    fecha = forms.DateField(label='¿Qué día fuiste?', widget=forms.DateInput(attrs={'type': 'date'}))

    def clean_fecha(self):
        fecha = self.cleaned_data['fecha']
        hoy = date.today()
        if fecha > hoy:
            raise forms.ValidationError('La visita no puede ser en el futuro.')
        if fecha.year < 1950:
            raise forms.ValidationError('Esa fecha no parece correcta.')
        return fecha
