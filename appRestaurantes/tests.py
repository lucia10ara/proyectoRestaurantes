"""Pruebas automáticas. Se ejecutan con:  python manage.py test appRestaurantes
Usan una base de datos temporal (no tocan la nuestra)."""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Ciudad, Perfil, Restaurante, Resena, Foto, Comentario, Guardado, Visita, MomentoComida


class Base(TestCase):
    """Datos mínimos: dos usuarios normales, una administradora y un restaurante."""

    @classmethod
    def setUpTestData(cls):
        cls.ciudad = Ciudad.objects.create(nombre='Bilbao', comunidad='País Vasco')
        cls.resto = Restaurante.objects.create(ciudad=cls.ciudad, nombre='Taberna Prueba', tipo_cocina='Pintxos', direccion='Calle 1')
        cls.ana = cls.usuario('ana')
        cls.bea = cls.usuario('bea')
        cls.admin = cls.usuario('admin', staff=True)

    @staticmethod
    def usuario(nombre, staff=False):
        u = User.objects.create_user(nombre, password='Contr4seña!xyz', is_staff=staff)
        Perfil.objects.create(usuario=u, ciudad=Ciudad.objects.first())
        return u

    def entrar(self, usuario):
        self.client.force_login(usuario)


class PaginasAntiguasTests(Base):
    """Lo que ya funcionaba tiene que seguir funcionando."""

    def test_paginas_publicas(self):
        for url in ['/', '/explorar/', '/restaurantes/', f'/restaurantes/{self.resto.id}/', '/perfiles/', '/ciudades/', '/login/', '/registro/']:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_publicar_resena_y_permisos(self):
        self.entrar(self.ana)
        r = self.client.post(reverse('crear_resena', args=[self.resto.id]), {'puntuacion': 4, 'titulo': 'Bien', 'texto': 'Rico'})
        self.assertEqual(r.status_code, 302)
        resena = Resena.objects.get(titulo='Bien')
        self.assertEqual(resena.autor.usuario, self.ana)
        self.entrar(self.bea)  #otra persona no puede borrarla
        self.assertEqual(self.client.post(reverse('borrar_resena', args=[resena.id])).status_code, 403)
        self.entrar(self.admin)  #la administradora sí
        self.assertEqual(self.client.post(reverse('borrar_resena', args=[resena.id])).status_code, 302)
        self.assertFalse(Resena.objects.filter(pk=resena.id).exists())

    def test_comentario_se_guarda(self):
        foto = Foto.objects.create(restaurante=self.resto, autor=self.ana.perfil, url='https://example.com/a.jpg')
        self.entrar(self.bea)
        self.client.post(reverse('comentar', args=['foto', foto.id]), {'texto': 'hola'})
        self.assertEqual(Comentario.objects.filter(foto=foto).count(), 1)

    def test_panel_solo_administradora(self):
        self.entrar(self.ana)
        self.assertEqual(self.client.get(reverse('panel')).status_code, 403)
        self.entrar(self.admin)
        self.assertEqual(self.client.get(reverse('panel')).status_code, 200)


class GuardarYVisitasTests(Base):
    """Bloque 0: guardar (pendiente) y visitas confirmadas."""

    def test_sin_sesion_pide_login(self):
        r = self.client.post(reverse('guardar_restaurante', args=[self.resto.id]))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('login'), r['Location'])
        self.assertEqual(Guardado.objects.count(), 0)

    def test_guardar_y_quitar(self):
        self.entrar(self.ana)
        self.client.post(reverse('guardar_restaurante', args=[self.resto.id]))
        self.assertTrue(Guardado.objects.filter(perfil=self.ana.perfil, restaurante=self.resto).exists())
        self.client.post(reverse('guardar_restaurante', args=[self.resto.id]))
        self.assertFalse(Guardado.objects.exists())

    def test_guardar_no_cuenta_como_visita(self):
        self.entrar(self.ana)
        self.client.post(reverse('guardar_restaurante', args=[self.resto.id]))
        self.assertEqual(Visita.objects.count(), 0)

    def test_guardar_por_ajax(self):
        self.entrar(self.ana)
        r = self.client.post(reverse('guardar_restaurante', args=[self.resto.id]), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(r.json(), {'guardado': True})

    def test_get_no_vale(self):
        self.entrar(self.ana)
        self.assertEqual(self.client.get(reverse('guardar_restaurante', args=[self.resto.id])).status_code, 405)
        self.assertEqual(self.client.get(reverse('marcar_visita', args=[self.resto.id])).status_code, 405)

    def test_marcar_visita(self):
        self.entrar(self.ana)
        ayer = date.today() - timedelta(days=1)
        self.client.post(reverse('marcar_visita', args=[self.resto.id]), {'fecha': ayer.isoformat()})
        v = Visita.objects.get()
        self.assertEqual((v.perfil.usuario, v.fecha, v.origen), (self.ana, ayer, 'boton'))

    def test_visita_repetida_el_mismo_dia_no_duplica(self):
        self.entrar(self.ana)
        for _ in range(2):
            self.client.post(reverse('marcar_visita', args=[self.resto.id]), {'fecha': date.today().isoformat()})
        self.assertEqual(Visita.objects.count(), 1)

    def test_visita_en_el_futuro_se_rechaza(self):
        self.entrar(self.ana)
        manana = date.today() + timedelta(days=1)
        self.client.post(reverse('marcar_visita', args=[self.resto.id]), {'fecha': manana.isoformat()})
        self.assertEqual(Visita.objects.count(), 0)

    def test_visita_sin_fecha_se_rechaza(self):
        self.entrar(self.ana)
        self.client.post(reverse('marcar_visita', args=[self.resto.id]), {'fecha': ''})
        self.assertEqual(Visita.objects.count(), 0)

    def test_solo_borro_mis_visitas(self):
        v = Visita.objects.create(perfil=self.ana.perfil, restaurante=self.resto, fecha=date.today())
        self.entrar(self.bea)
        self.assertEqual(self.client.post(reverse('borrar_visita', args=[v.id])).status_code, 403)
        self.entrar(self.admin)  #el diario es personal: ni la administradora lo toca
        self.assertEqual(self.client.post(reverse('borrar_visita', args=[v.id])).status_code, 403)
        self.entrar(self.ana)
        self.client.post(reverse('borrar_visita', args=[v.id]))
        self.assertFalse(Visita.objects.exists())

    def test_next_externo_no_se_sigue(self):
        self.entrar(self.ana)
        r = self.client.post(reverse('guardar_restaurante', args=[self.resto.id]), {'next': 'https://malo.example/'})
        self.assertEqual(r['Location'], reverse('detalle_restaurante', args=[self.resto.id]))

    def test_ficha_muestra_estado(self):
        self.entrar(self.ana)
        Guardado.objects.create(perfil=self.ana.perfil, restaurante=self.resto)
        html = self.client.get(reverse('detalle_restaurante', args=[self.resto.id])).content.decode()
        self.assertIn('Guardado en pendientes', html)
        self.assertIn('Confirmar visita', html)


class DatosNuevosTests(Base):
    """Bloque 0: campos nuevos del restaurante."""

    def test_momentos_creados_por_migracion(self):
        self.assertEqual(list(MomentoComida.objects.values_list('clave', flat=True)), ['desayuno', 'brunch', 'comida', 'merienda', 'cena'])

    def test_lo_desconocido_no_se_enseña(self):
        html = self.client.get(reverse('detalle_restaurante', args=[self.resto.id])).content.decode()
        self.assertNotIn('Terraza', html)  #terraza = None (no se sabe)
        self.resto.terraza = False
        self.resto.save()
        html = self.client.get(reverse('detalle_restaurante', args=[self.resto.id])).content.decode()
        self.assertIn('Sin terraza', html)

    def test_admin_valida_coordenadas(self):
        self.entrar(self.admin)
        url = reverse('editar_restaurante', args=[self.resto.id])
        base = {'nombre': 'Taberna Prueba', 'tipo_cocina': 'Pintxos', 'direccion': 'Calle 1', 'admite_ninos': 'on',
                'terraza': 'unknown', 'menu_del_dia': 'unknown', 'vegetariano': 'unknown', 'vegano': 'unknown',
                'para_grupos': 'unknown', 'accesible': 'unknown'}
        self.client.post(url, {**base, 'latitud': '43.26'})  #falta la longitud
        self.resto.refresh_from_db()
        self.assertIsNone(self.resto.latitud)
        self.client.post(url, {**base, 'latitud': '43.26', 'longitud': '-2.93'})
        self.resto.refresh_from_db()
        self.assertEqual((self.resto.latitud, self.resto.longitud), (43.26, -2.93))

    def test_restaurante_nuevo_tiene_fecha_de_alta(self):
        r = Restaurante.objects.create(ciudad=self.ciudad, nombre='Nuevo', tipo_cocina='X', direccion='Y')
        self.assertIsNotNone(r.fecha_alta)
