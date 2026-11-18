from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Ciudad, Perfil


#Formulario de registro: el de Django (usuario + contraseña dos veces) más la ciudad y la biografía, que van en el Perfil
class RegistroForm(UserCreationForm):
    ciudad = forms.ModelChoiceField(queryset=Ciudad.objects.all(), required=False,
                                    empty_label='— Elige tu ciudad —',
                                    help_text='La usaremos para enseñarte primero los sitios de tu ciudad en Explorar.')
    biografia = forms.CharField(max_length=250, required=False, label='Biografía',
                                help_text='Opcional: una frase sobre ti.')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username',)

    def save(self, commit=True):
        usuario = super().save(commit=commit)
        if commit:
            #cada usuario tiene su perfil (relación uno a uno), lo creamos a la vez
            Perfil.objects.create(usuario=usuario,
                                  ciudad=self.cleaned_data['ciudad'],
                                  biografia=self.cleaned_data['biografia'] or None)
        return usuario
