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
        r = self.client.post(reverse('crear_resena', args=[self.resto.id]), {
            'puntuacion': 4, 'nota_comida': 4, 'nota_servicio': 4, 'nota_ambiente': 4, 'nota_calidad_precio': 4,
            'titulo': 'Bien', 'texto': 'Rico'})
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


RESENA_COMPLETA = {'puntuacion': 5, 'nota_comida': 5, 'nota_servicio': 4, 'nota_ambiente': 3, 'nota_calidad_precio': 4,
                   'titulo': 'Muy bien', 'texto': 'Todo rico'}


class ResenasPorCategoriaTests(Base):
    """Bloque 1: notas por categoría y visita al reseñar."""

    def crear(self, **extra):
        return self.client.post(reverse('crear_resena', args=[self.resto.id]), {**RESENA_COMPLETA, **extra})

    def test_nueva_sin_categorias_no_se_guarda(self):
        self.entrar(self.ana)
        self.client.post(reverse('crear_resena', args=[self.resto.id]), {'puntuacion': 4, 'titulo': 'x', 'texto': 'y'})
        self.assertFalse(Resena.objects.exists())

    def test_nueva_con_estuve_crea_visita(self):
        self.entrar(self.ana)
        self.crear(estuve='on', fecha_visita=date.today().isoformat())
        r = Resena.objects.get()
        self.assertEqual((r.nota_comida, r.nota_calidad_precio), (5, 4))
        v = Visita.objects.get()
        self.assertEqual((v.perfil.usuario, v.origen), (self.ana, 'resena'))

    def test_sin_estuve_no_hay_visita(self):
        self.entrar(self.ana)
        self.crear()
        self.assertEqual(Resena.objects.count(), 1)
        self.assertEqual(Visita.objects.count(), 0)

    def test_visita_futura_al_resenar_se_rechaza(self):
        self.entrar(self.ana)
        self.crear(estuve='on', fecha_visita=(date.today() + timedelta(days=3)).isoformat())
        self.assertFalse(Resena.objects.exists())

    def test_editar_resena_antigua_sin_categorias(self):
        antigua = Resena.objects.create(restaurante=self.resto, autor=self.ana.perfil, puntuacion=3, titulo='Vieja', texto='t')
        self.entrar(self.ana)
        self.client.post(reverse('editar_resena', args=[antigua.id]), {'puntuacion': 4, 'titulo': 'Vieja', 'texto': 't'})
        antigua.refresh_from_db()
        self.assertEqual(antigua.puntuacion, 4)
        self.assertIsNone(antigua.nota_comida)

    def test_ficha_muestra_medias_por_categoria(self):
        Resena.objects.create(restaurante=self.resto, autor=self.ana.perfil, **RESENA_COMPLETA)
        Resena.objects.create(restaurante=self.resto, autor=self.bea.perfil, puntuacion=3, titulo='Antigua', texto='t')
        html = self.client.get(reverse('detalle_restaurante', args=[self.resto.id])).content.decode()
        self.assertIn('Calidad-precio', html)
        self.assertIn('Según 1 reseña con notas por categoría', html)


class GenteEnRestauranteTests(Base):
    """Bloque 1: qué personas a las que sigo han estado, lo recomiendan, lo tienen pendiente o han publicado."""

    def setUp(self):
        self.bea.perfil.siguiendo.add(self.ana.perfil)  #bea sigue a ana

    def ficha(self):
        self.entrar(self.bea)
        return self.client.get(reverse('detalle_restaurante', args=[self.resto.id])).context['social']

    def test_sin_seguir_a_nadie(self):
        self.entrar(self.ana)  #ana no sigue a nadie
        social = self.client.get(reverse('detalle_restaurante', args=[self.resto.id])).context['social']
        self.assertFalse(social['sigo_a_alguien'])

    def test_estado_solo_con_visita_confirmada(self):
        Foto.objects.create(restaurante=self.resto, autor=self.ana.perfil, url='https://example.com/a.jpg')
        social = self.ficha()
        self.assertEqual(social['estado'], [])  #publicar una foto no es haber estado
        self.assertEqual(len(social['publicado']), 1)
        Visita.objects.create(perfil=self.ana.perfil, restaurante=self.resto, fecha=date(2026, 11, 2))
        social = self.ficha()
        self.assertEqual(social['estado'][0]['detalle'], 'estuvo el 02/11/2026')

    def test_recomienda_solo_con_4_o_5(self):
        Resena.objects.create(restaurante=self.resto, autor=self.ana.perfil, puntuacion=3, titulo='Meh', texto='t')
        self.assertEqual(self.ficha()['recomiendan'], [])
        Resena.objects.create(restaurante=self.resto, autor=self.ana.perfil, puntuacion=5, titulo='Top', texto='t')
        self.assertEqual(len(self.ficha()['recomiendan']), 1)

    def test_pendiente_y_no_cuenta_gente_que_no_sigo(self):
        Guardado.objects.create(perfil=self.ana.perfil, restaurante=self.resto)
        Guardado.objects.create(perfil=self.admin.perfil, restaurante=self.resto)  #a esta no la sigue
        pendiente = self.ficha()['pendiente']
        self.assertEqual([p['perfil'].usuario.username for p in pendiente], ['ana'])


class FiltrosAvanzadosTests(Base):
    """Bloque 1: los filtros se combinan y lo desconocido no se da por confirmado."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.con_terraza = Restaurante.objects.create(ciudad=cls.ciudad, nombre='Con terraza', tipo_cocina='X', direccion='A',
                                                     terraza=True, vegetariano=True, precio=1, precio_max_persona=15)
        cls.sin_terraza = Restaurante.objects.create(ciudad=cls.ciudad, nombre='Sin terraza', tipo_cocina='X', direccion='B',
                                                     terraza=False, precio=3, precio_max_persona=60)
        cls.cena = MomentoComida.objects.get(clave='cena')
        cls.con_terraza.momentos.add(cls.cena)

    def nombres(self, query):
        r = self.client.get('/restaurantes/?' + query)
        self.assertEqual(r.status_code, 200)
        return sorted(x.nombre for x in r.context['page_obj'])

    def test_terraza_solo_confirmada(self):
        self.assertEqual(self.nombres('terraza=1'), ['Con terraza'])  #el de terraza desconocida no sale

    def test_combinados(self):
        self.assertEqual(self.nombres('terraza=1&vegetariano=1&precio=1&momento=cena'), ['Con terraza'])
        self.assertEqual(self.nombres('terraza=1&precio=3'), [])

    def test_precio_maximo_excluye_desconocidos(self):
        self.assertEqual(self.nombres('precio_max=20'), ['Con terraza'])

    def test_amigos_guardados_y_fotos(self):
        self.bea.perfil.siguiendo.add(self.ana.perfil)
        Resena.objects.create(restaurante=self.sin_terraza, autor=self.ana.perfil, puntuacion=5, titulo='t', texto='t')
        Guardado.objects.create(perfil=self.bea.perfil, restaurante=self.con_terraza)
        Foto.objects.create(restaurante=self.resto, autor=self.ana.perfil, url='https://example.com/a.jpg')
        self.entrar(self.bea)
        self.assertEqual(self.nombres('amigos=1'), ['Sin terraza'])
        self.assertEqual(self.nombres('guardados=1'), ['Con terraza'])
        self.assertEqual(self.nombres('con_fotos=1'), ['Taberna Prueba'])

    def test_valores_raros_no_rompen(self):
        self.assertEqual(self.client.get('/restaurantes/?precio=abc&precio_max=-5&ciudad=xx&momento=nada').status_code, 200)
        self.assertEqual(self.client.get('/explorar/?terraza=1&precio=9').status_code, 200)

    def test_sin_sesion_se_ignoran_los_filtros_personales(self):
        self.assertEqual(len(self.nombres('guardados=1')), 3)


class MapaTests(Base):
    """Bloque 2: el mapa solo enseña lo que tiene ubicación y respeta los filtros."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.resto.latitud, cls.resto.longitud = 43.26, -2.93
        cls.resto.save()
        cls.sin_sitio = Restaurante.objects.create(ciudad=cls.ciudad, nombre='Sin ubicación', tipo_cocina='Pintxos', direccion='Calle 2')
        cls.lejos = Restaurante.objects.create(ciudad=cls.ciudad, nombre='En Madrid', tipo_cocina='Italiana', direccion='Calle 3',
                                               latitud=40.41, longitud=-3.70, terraza=True)
        Resena.objects.create(restaurante=cls.resto, autor=cls.ana.perfil, puntuacion=4, titulo='Bien', texto='ok')
        Resena.objects.create(restaurante=cls.resto, autor=cls.bea.perfil, puntuacion=5, titulo='Genial', texto='ok')

    BILBAO = {'sur': 43.0, 'norte': 43.5, 'oeste': -3.2, 'este': -2.7}

    def datos(self, **params):
        r = self.client.get(reverse('mapa_datos'), params)
        return r, r.json()

    def test_paginas(self):
        self.assertEqual(self.client.get(reverse('mapa')).status_code, 200)
        self.assertEqual(self.client.get(reverse('mapa'), {'foco': self.resto.id, 'terraza': 1}).status_code, 200)
        self.assertEqual(self.client.get(reverse('mapa'), {'foco': 'x"><script>'}).status_code, 200)

    def test_solo_la_zona_visible_y_con_ubicacion(self):
        r, d = self.datos(**self.BILBAO)
        self.assertEqual([x['id'] for x in d['restaurantes']], [self.resto.id])  #ni el de Madrid ni el que no tiene ubicación
        self.assertEqual(d['total'], 1)
        self.assertEqual(d['restaurantes'][0]['media'], 4.5)
        self.assertEqual(d['restaurantes'][0]['resenas'], 2)

    def test_respeta_filtros_y_buscador(self):
        todo = {'sur': 35, 'norte': 45, 'oeste': -10, 'este': 5}
        self.assertEqual(self.datos(**todo)[1]['total'], 2)
        self.assertEqual([x['id'] for x in self.datos(terraza=1, **todo)[1]['restaurantes']], [self.lejos.id])
        self.assertEqual([x['id'] for x in self.datos(q='pintxo', **todo)[1]['restaurantes']], [self.resto.id])
        self.assertEqual(self.datos(precio=2, **todo)[1]['total'], 0)  #el precio desconocido no cuenta como confirmado

    def test_limites_invalidos(self):
        self.assertEqual(self.client.get(reverse('mapa_datos')).status_code, 400)
        for malo in ['nan', 'inf', 'abc', '999']:
            r, _ = self.datos(**{**self.BILBAO, 'sur': malo})
            self.assertEqual(r.status_code, 400, malo)

    def test_encuadre_inicial_y_foco(self):
        _, d = self.datos(inicial=1, foco=self.resto.id)
        self.assertEqual(d['total'], 2)
        self.assertEqual(d['zona'], [[40.41, -3.70], [43.26, -2.93]])
        self.assertEqual(d['foco']['id'], self.resto.id)
        _, d = self.datos(inicial=1, foco=self.sin_sitio.id)  #sin coordenadas no se puede enfocar
        self.assertIsNone(d['foco'])
        _, d = self.datos(inicial=1, precio=3)
        self.assertIsNone(d['zona'])

    def test_limite_de_puntos(self):
        from . import views
        Restaurante.objects.bulk_create([Restaurante(ciudad=self.ciudad, nombre=f'Bar {i}', tipo_cocina='Bar', direccion=f'Calle {i}',
                                                     latitud=43.2, longitud=-2.9) for i in range(views.LIMITE_MAPA + 5)])
        _, d = self.datos(**self.BILBAO)
        self.assertEqual(len(d['restaurantes']), views.LIMITE_MAPA)
        self.assertEqual(d['total'], views.LIMITE_MAPA + 6)  #el total real, para avisar de que faltan por enseñar

    def test_enlaces_lista_y_ficha(self):
        self.assertContains(self.client.get(reverse('lista_restaurantes'), {'terraza': 1}), '/mapa/?terraza=1')
        self.assertContains(self.client.get(f'/restaurantes/{self.resto.id}/'), f'/mapa/?foco={self.resto.id}')
        self.assertNotContains(self.client.get(f'/restaurantes/{self.sin_sitio.id}/'), 'Ver en el mapa')
