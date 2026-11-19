"""Pruebas automáticas. Se ejecutan con:  python manage.py test appRestaurantes
Usan una base de datos temporal (no tocan la nuestra)."""
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from django.urls import reverse

from .models import Ciudad, Perfil, Restaurante, Resena, Foto, Comentario, Guardado, Visita, MomentoComida, Coleccion, ElementoColeccion, Notificacion, Plan, Invitacion, Historia


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


class ColeccionesTests(Base):
    """Bloque 3: colecciones propias, públicas o privadas."""

    def setUp(self):
        self.publica = Coleccion.objects.create(perfil=self.ana.perfil, nombre='Cumpleaños')
        self.privada = Coleccion.objects.create(perfil=self.ana.perfil, nombre='Secreta', publica=False)
        ElementoColeccion.objects.create(coleccion=self.privada, restaurante=self.resto)

    def test_crear_y_nombre_repetido(self):
        self.entrar(self.bea)
        r = self.client.post(reverse('crear_coleccion'), {'nombre': 'Cenas', 'publica': 'on'})
        self.assertEqual(self.bea.perfil.colecciones.count(), 1)
        self.assertRedirects(r, reverse('detalle_coleccion', args=[self.bea.perfil.colecciones.get().pk]))
        r = self.client.post(reverse('crear_coleccion'), {'nombre': 'cenas'})  #mismo nombre sin importar mayúsculas
        self.assertContains(r, 'Ya tienes una colección con ese nombre')
        self.assertEqual(self.bea.perfil.colecciones.count(), 1)

    def test_crear_exige_sesion(self):
        self.assertEqual(self.client.post(reverse('crear_coleccion'), {'nombre': 'X'}).status_code, 302)
        self.assertEqual(Coleccion.objects.filter(nombre='X').count(), 0)

    def test_privada_solo_su_dueno(self):
        url = reverse('detalle_coleccion', args=[self.privada.pk])
        self.assertEqual(self.client.get(url).status_code, 404)  #sin sesión
        self.entrar(self.bea)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.get(reverse('detalle_coleccion', args=[self.publica.pk])).status_code, 200)
        self.entrar(self.ana)
        self.assertEqual(self.client.get(url).status_code, 200)
        self.entrar(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_listas_no_enseñan_privadas_a_otros(self):
        url = reverse('colecciones_de_perfil', args=[self.ana.perfil.pk])
        self.entrar(self.bea)
        r = self.client.get(url)
        self.assertContains(r, 'Cumpleaños')
        self.assertNotContains(r, 'Secreta')
        self.assertContains(self.client.get(reverse('detalle_perfil', args=[self.ana.perfil.pk])), '<strong>1</strong> colecciones')
        self.entrar(self.ana)
        self.assertContains(self.client.get(url), 'Secreta')

    def test_anadir_desde_la_ficha(self):
        self.entrar(self.bea)
        url = reverse('anadir_a_coleccion', args=[self.resto.pk])
        self.client.post(url, {'nombre_nueva': 'Con amigos'})  #crea y añade
        nueva = self.bea.perfil.colecciones.get(nombre='Con amigos')
        self.assertEqual(nueva.elementos.count(), 1)
        self.client.post(url, {'nombre_nueva': 'con AMIGOS'})  #misma colección, no se duplica
        self.assertEqual(self.bea.perfil.colecciones.count(), 1)
        self.assertEqual(nueva.elementos.count(), 1)
        self.client.post(url, {'coleccion': self.publica.pk})  #la de otra persona no vale
        self.assertEqual(self.publica.elementos.count(), 0)
        self.client.post(url, {'coleccion': 'abc'})  #id inválido: aviso, sin error 500
        self.assertContains(self.client.get(f'/restaurantes/{self.resto.pk}/'), 'Con amigos')

    def test_solo_el_dueno_cambia_y_la_admin_borra(self):
        self.entrar(self.bea)
        self.assertEqual(self.client.get(reverse('editar_coleccion', args=[self.publica.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('borrar_coleccion', args=[self.publica.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('quitar_de_coleccion', args=[self.privada.pk, self.resto.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse('nota_en_coleccion', args=[self.privada.pk, self.resto.pk]), {'nota': 'x'}).status_code, 403)
        self.assertEqual(self.client.get(reverse('borrar_coleccion', args=[self.publica.pk])).status_code, 405)  #solo POST
        self.assertEqual(Coleccion.objects.count(), 2)
        self.entrar(self.admin)
        self.client.post(reverse('borrar_coleccion', args=[self.publica.pk]))
        self.assertEqual(Coleccion.objects.count(), 1)

    def test_nota_y_quitar(self):
        self.entrar(self.ana)
        self.client.post(reverse('nota_en_coleccion', args=[self.privada.pk, self.resto.pk]), {'nota': 'Pedir el pulpo'})
        self.assertEqual(self.privada.elementos.get().nota, 'Pedir el pulpo')
        self.client.post(reverse('quitar_de_coleccion', args=[self.privada.pk, self.resto.pk]))
        self.assertEqual(self.privada.elementos.count(), 0)
        self.assertTrue(Restaurante.objects.filter(pk=self.resto.pk).exists())  #el restaurante sigue existiendo

    def test_filtro_del_mapa_respeta_privacidad(self):
        self.resto.latitud, self.resto.longitud = 43.26, -2.93
        self.resto.save()
        zona = {'sur': 43, 'norte': 44, 'oeste': -3.5, 'este': -2.5}
        url = reverse('mapa_datos')
        self.assertEqual(self.client.get(url, {**zona, 'coleccion': self.privada.pk}).json()['total'], 0)
        self.entrar(self.bea)
        self.assertEqual(self.client.get(url, {**zona, 'coleccion': self.privada.pk}).json()['total'], 0)
        self.entrar(self.ana)
        self.assertEqual(self.client.get(url, {**zona, 'coleccion': self.privada.pk}).json()['total'], 1)
        self.assertEqual(self.client.get(url, {**zona, 'coleccion': 'x'}).json()['total'], 0)

    def test_borrar_restaurante_o_usuario_limpia(self):
        self.resto.delete()
        self.assertEqual(ElementoColeccion.objects.count(), 0)
        self.ana.delete()
        self.assertEqual(Coleccion.objects.count(), 0)


class AvisosTests(Base):
    """Bloque 4 (parte 1): notificaciones."""

    def test_seguir_avisa_una_vez(self):
        self.entrar(self.bea)
        url = reverse('seguir', args=[self.ana.perfil.pk])
        self.client.post(url); self.client.post(url); self.client.post(url)  #seguir, dejar, seguir otra vez
        self.assertEqual(Notificacion.objects.filter(destinatario=self.ana.perfil, tipo='seguidor').count(), 1)

    def test_comentar_avisa_al_autor_pero_no_a_uno_mismo(self):
        resena = Resena.objects.create(restaurante=self.resto, autor=self.ana.perfil, puntuacion=4, titulo='t', texto='x')
        self.entrar(self.ana)
        self.client.post(reverse('comentar', args=['resena', resena.pk]), {'texto': 'yo mismo'})
        self.assertEqual(Notificacion.objects.count(), 0)
        self.entrar(self.bea)
        self.client.post(reverse('comentar', args=['resena', resena.pk]), {'texto': 'qué bien'})
        aviso = Notificacion.objects.get()
        self.assertEqual(aviso.destinatario, self.ana.perfil)
        self.assertEqual(aviso.url, reverse('detalle_resena', args=[resena.pk]))

    def test_pagina_de_avisos_y_contador(self):
        Notificacion.objects.create(destinatario=self.ana.perfil, actor=self.bea.perfil, tipo='seguidor', texto='bea te sigue')
        Notificacion.objects.create(destinatario=self.bea.perfil, tipo='seguidor', texto='aviso de bea')
        self.assertEqual(self.client.get('/avisos/').status_code, 302)  #sin sesión
        self.entrar(self.ana)
        self.assertContains(self.client.get('/'), 'insignia')  #contador en el menú
        r = self.client.get('/avisos/')
        self.assertContains(r, 'bea te sigue')
        self.assertNotContains(r, 'aviso de bea')  #los de otro usuario no se ven
        self.assertNotContains(self.client.get('/'), 'insignia')  #ya leído
        self.client.post('/avisos/borrar-leidos/')
        self.assertEqual(Notificacion.objects.filter(destinatario=self.ana.perfil).count(), 0)
        self.assertEqual(Notificacion.objects.filter(destinatario=self.bea.perfil).count(), 1)


class PlanesTests(Base):
    """Bloque 4 (parte 2): planes entre amigos."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cai = cls.usuario('cai')  #ana y bea son amigas; cai solo es seguida por ana (no amiga)
        cls.ana.perfil.siguiendo.add(cls.bea.perfil, cls.cai.perfil)
        cls.bea.perfil.siguiendo.add(cls.ana.perfil)

    def manana(self, horas=24):
        return (timezone.localtime() + timedelta(hours=horas)).strftime('%Y-%m-%dT%H:%M')

    def crear(self, **extra):
        self.entrar(self.ana)
        datos = {'cuando': self.manana(), 'mensaje': 'Cenamos', 'invitados': [self.bea.perfil.pk], **extra}
        return self.client.post(reverse('crear_plan', args=[self.resto.pk]), datos)

    def test_crear_avisa_y_solo_invita_a_amigos(self):
        r = self.crear()
        plan = Plan.objects.get()
        self.assertRedirects(r, reverse('detalle_plan', args=[plan.pk]))
        self.assertEqual(plan.invitaciones.get().perfil, self.bea.perfil)
        aviso = Notificacion.objects.get(destinatario=self.bea.perfil)
        self.assertIn('te ha invitado', aviso.texto)
        self.assertEqual(aviso.url, reverse('detalle_plan', args=[plan.pk]))

    def test_no_se_puede_invitar_a_quien_no_es_amigo(self):
        self.crear(invitados=[self.cai.perfil.pk])
        self.assertEqual(Plan.objects.count(), 0)
        self.crear(invitados=[])  #al menos uno
        self.assertEqual(Plan.objects.count(), 0)

    def test_fecha_pasada_rechazada(self):
        self.crear(cuando=self.manana(-5))
        self.assertEqual(Plan.objects.count(), 0)
        self.crear(cuando='basura')
        self.assertEqual(Plan.objects.count(), 0)

    def test_sin_amigos_no_hay_formulario(self):
        self.entrar(self.cai)
        r = self.client.get(reverse('crear_plan', args=[self.resto.pk]))
        self.assertRedirects(r, reverse('detalle_restaurante', args=[self.resto.pk]))

    def test_solo_lo_ve_quien_participa(self):
        self.crear()
        url = reverse('detalle_plan', args=[Plan.objects.get().pk])
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 404)
        self.entrar(self.cai)
        self.assertEqual(self.client.get(url).status_code, 404)
        for u in (self.ana, self.bea, self.admin):
            self.entrar(u)
            self.assertEqual(self.client.get(url).status_code, 200, u)

    def test_responder(self):
        self.crear()
        plan = Plan.objects.get()
        url = reverse('responder_plan', args=[plan.pk])
        self.entrar(self.cai)
        self.assertEqual(self.client.post(url, {'respuesta': 'si'}).status_code, 404)  #no invitada
        self.entrar(self.ana)
        self.assertEqual(self.client.post(url, {'respuesta': 'si'}).status_code, 404)  #la creadora no tiene invitación
        self.entrar(self.bea)
        self.assertEqual(self.client.post(url, {'respuesta': 'quizas'}).status_code, 403)
        self.client.post(url, {'respuesta': 'si'})
        self.assertEqual(plan.invitaciones.get().estado, 'si')
        self.assertTrue(Notificacion.objects.filter(destinatario=self.ana.perfil, texto__contains='irá').exists())
        self.client.post(url, {'respuesta': 'si'})  #repetir no duplica el aviso
        self.assertEqual(Notificacion.objects.filter(destinatario=self.ana.perfil, texto__contains='irá').count(), 1)

    def test_cancelar_solo_la_creadora(self):
        self.crear()
        plan = Plan.objects.get()
        url = reverse('cancelar_plan', args=[plan.pk])
        self.entrar(self.bea)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.entrar(self.ana)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        plan.refresh_from_db()
        self.assertTrue(plan.cancelado)
        self.assertTrue(Notificacion.objects.filter(destinatario=self.bea.perfil, texto__contains='cancelado').exists())
        self.entrar(self.bea)  #un plan cancelado ya no admite respuestas
        self.client.post(reverse('responder_plan', args=[plan.pk]), {'respuesta': 'si'})
        self.assertEqual(plan.invitaciones.get().estado, 'pendiente')

    def test_listas_y_visita_tras_el_plan(self):
        self.crear()
        plan = Plan.objects.get()
        self.entrar(self.bea)
        self.assertContains(self.client.get(reverse('mis_planes')), 'Invitaciones sin responder')
        #el plan pasa: se ofrece apuntar la visita, pero no se crea sola
        Plan.objects.filter(pk=plan.pk).update(cuando=timezone.now() - timedelta(days=1))
        Invitacion.objects.filter(plan=plan).update(estado='si')
        r = self.client.get(reverse('detalle_plan', args=[plan.pk]))
        self.assertContains(r, 'apuntar la visita')
        self.assertEqual(Visita.objects.count(), 0)
        self.client.post(reverse('marcar_visita', args=[self.resto.pk]), {'fecha': (date.today() - timedelta(days=1)).isoformat(), 'next': r.request['PATH_INFO']})
        self.assertEqual(Visita.objects.filter(perfil=self.bea.perfil).count(), 1)


class HistoriasTests(Base):
    """Bloque 5: historias de 24 horas."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cai = cls.usuario('cai')
        cls.bea.perfil.siguiendo.add(cls.ana.perfil)  #bea sigue a ana; cai no

    def historia(self, **extra):
        return Historia.objects.create(autor=self.ana.perfil, restaurante=self.resto, url='https://ejemplo.com/a.jpg', texto='Rico', **extra)

    def test_caduca_a_las_24_horas(self):
        h = self.historia()
        self.assertAlmostEqual((h.caduca - h.creada).total_seconds(), 24 * 3600, delta=5)
        self.assertEqual(Historia.activas().count(), 1)
        Historia.objects.filter(pk=h.pk).update(caduca=timezone.now() - timedelta(seconds=1))
        self.assertEqual(Historia.activas().count(), 0)

    def test_quien_puede_verla(self):
        h = self.historia()
        url = reverse('ver_historias', args=[self.ana.perfil.pk])
        self.assertEqual(self.client.get(url).status_code, 302)  #sin sesión: al login
        self.entrar(self.cai)
        self.assertEqual(self.client.get(url).status_code, 404)  #no la sigue
        self.entrar(self.bea)
        self.assertContains(self.client.get(url), 'Rico')
        self.assertEqual(list(h.vista_por.all()), [self.bea.perfil])
        self.entrar(self.ana)
        r = self.client.get(url)
        self.assertContains(r, 'Vista por 1 persona')
        self.entrar(self.admin)
        self.assertEqual(self.client.get(url).status_code, 200)

    def test_caducada_no_se_ve(self):
        h = self.historia()
        Historia.objects.filter(pk=h.pk).update(caduca=timezone.now() - timedelta(minutes=1))
        self.entrar(self.ana)
        self.assertEqual(self.client.get(reverse('ver_historias', args=[self.ana.perfil.pk])).status_code, 404)

    def test_tira_en_el_inicio(self):
        self.historia()
        self.entrar(self.bea)
        r = self.client.get('/')
        self.assertContains(r, 'tira-historias')
        self.assertContains(r, 'sin-ver')
        self.client.get(reverse('ver_historias', args=[self.ana.perfil.pk]))
        self.assertNotContains(self.client.get('/'), 'sin-ver')  #ya vista
        self.entrar(self.cai)
        self.assertNotContains(self.client.get('/'), 'tira-historias')

    def test_crear_con_enlace_sin_imagen_y_limite(self):
        self.entrar(self.ana)
        url = reverse('crear_historia', args=[self.resto.pk])
        self.client.post(url, {'texto': 'sin imagen'})
        self.assertEqual(Historia.objects.count(), 0)
        self.client.post(url, {'url': 'https://ejemplo.com/b.jpg', 'texto': 'ok'})
        self.assertEqual(Historia.objects.get().autor, self.ana.perfil)
        from . import views_historias
        for _ in range(views_historias.MAX_HISTORIAS_ACTIVAS):
            self.historia()
        self.client.post(url, {'url': 'https://ejemplo.com/c.jpg'})
        self.assertEqual(Historia.objects.count(), views_historias.MAX_HISTORIAS_ACTIVAS + 1)
        self.client.logout()
        self.assertEqual(self.client.post(url, {'url': 'https://ejemplo.com/d.jpg'}).status_code, 302)

    def test_solo_borra_el_autor_o_la_admin(self):
        h = self.historia()
        url = reverse('borrar_historia', args=[h.pk])
        self.entrar(self.bea)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.assertEqual(self.client.get(url).status_code, 405)
        self.entrar(self.admin)
        self.client.post(url)
        self.assertEqual(Historia.objects.count(), 0)

    def test_comando_limpia_solo_caducadas(self):
        from django.core.management import call_command
        viva, muerta = self.historia(), self.historia()
        Historia.objects.filter(pk=muerta.pk).update(caduca=timezone.now() - timedelta(hours=1))
        call_command('limpiar_historias', stdout=__import__('io').StringIO())
        self.assertEqual(list(Historia.objects.values_list('pk', flat=True)), [viva.pk])


class DiarioTests(Base):
    """Bloque 6: diario, pasaporte y retos (solo cuentan las visitas confirmadas)."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.vigo = Ciudad.objects.create(nombre='Vigo', comunidad='Galicia')
        cls.pizzeria = Restaurante.objects.create(ciudad=cls.vigo, nombre='Pizzería', tipo_cocina='Pizzería', direccion='C 9')

    def visita(self, resto, dias_atras=0, perfil=None):
        return Visita.objects.create(perfil=perfil or self.ana.perfil, restaurante=resto, fecha=date.today() - timedelta(days=dias_atras))

    def test_exigen_sesion_y_son_personales(self):
        for url in ('/diario/', '/diario/pasaporte/', '/diario/retos/'):
            self.assertEqual(self.client.get(url).status_code, 302, url)
        self.visita(self.resto)
        self.entrar(self.bea)
        self.assertNotContains(self.client.get('/diario/'), 'Taberna Prueba')  #las visitas de ana no salen a bea

    def test_diario_agrupa_por_mes_y_enlaza_resena(self):
        self.visita(self.resto, 0)
        self.visita(self.resto, 70)
        Resena.objects.create(restaurante=self.resto, autor=self.ana.perfil, puntuacion=5, titulo='t', texto='x')
        self.entrar(self.ana)
        r = self.client.get('/diario/')
        self.assertEqual(len(r.context['meses']), 2)
        self.assertContains(r, 'mi reseña (5★)')

    def test_borrar_visita_desde_el_diario_quita_el_sello(self):
        v = self.visita(self.pizzeria)
        self.entrar(self.ana)
        self.assertContains(self.client.get('/diario/pasaporte/'), 'Vigo')
        r = self.client.post(reverse('borrar_visita', args=[v.pk]), {'next': '/diario/'})
        self.assertRedirects(r, '/diario/')
        self.assertNotContains(self.client.get('/diario/pasaporte/'), 'Vigo')

    def test_pasaporte_cuenta_ciudades_comunidades_y_cocinas(self):
        self.visita(self.resto, 5)
        self.visita(self.pizzeria, 1)
        self.visita(self.pizzeria, 0)  #otro día al mismo sitio: no duplica sellos
        from . import logros
        e = logros.estadisticas(self.ana.perfil)
        self.assertEqual((e['total_visitas'], e['n_restaurantes']), (3, 2))
        self.assertEqual([c['ciudad'].nombre for c in e['ciudades']], ['Bilbao', 'Vigo'])
        self.assertEqual({c['nombre'] for c in e['comunidades']}, {'País Vasco', 'Galicia'})
        self.assertEqual([c['clave'] for c in e['cocinas']], ['tapas', 'pizza'])

    def test_solo_cuentan_visitas_confirmadas(self):
        Guardado.objects.create(perfil=self.ana.perfil, restaurante=self.resto)
        Foto.objects.create(restaurante=self.resto, autor=self.ana.perfil, url='https://e.com/a.jpg')
        from . import logros
        e = logros.estadisticas(self.ana.perfil)
        self.assertEqual((e['total_visitas'], e['n_restaurantes'], len(e['ciudades'])), (0, 0, 0))
        self.assertFalse(any(r['hecho'] for r in logros.retos(e)))

    def test_retos(self):
        from . import logros
        for i in range(3):
            self.visita(self.resto, i)  #3 días distintos en el mismo sitio
        self.visita(self.pizzeria, 0)
        retos = {r['nombre']: r for r in logros.retos(logros.estadisticas(self.ana.perfil))}
        self.assertTrue(retos['Primer sitio']['hecho'])
        self.assertTrue(retos['Cliente fijo']['hecho'])
        self.assertTrue(retos['Cambio de aires']['hecho'])
        self.assertFalse(retos['Diez sitios']['hecho'])
        self.assertEqual((retos['Diez sitios']['actual'], retos['Diez sitios']['porcentaje']), (2, 20))
        self.entrar(self.ana)
        self.assertContains(self.client.get('/diario/retos/'), '¡Conseguido!')

    def test_mes_goloso_solo_cuenta_este_mes(self):
        from . import logros
        hoy = date(2026, 11, 20)
        for dia in (1, 2, 3, 4):
            Visita.objects.create(perfil=self.ana.perfil, restaurante=self.resto, fecha=date(2026, 10, dia))
        self.assertEqual(logros.estadisticas(self.ana.perfil, hoy=hoy)['visitas_este_mes'], 0)
        self.assertEqual(logros.estadisticas(self.ana.perfil, hoy=date(2026, 10, 20))['visitas_este_mes'], 4)


class DescubreTests(Base):
    """Bloque 7: Para ti, Novedades, Joyas y Ruleta."""

    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.cai = cls.usuario('cai')
        cls.ana.perfil.siguiendo.add(cls.bea.perfil)  #ana sigue a bea
        cls.otro = Restaurante.objects.create(ciudad=cls.ciudad, nombre='Bar Recomendado', tipo_cocina='Tapas', direccion='C 2', admite_perros=False)
        cls.perro = Restaurante.objects.create(ciudad=cls.ciudad, nombre='Bar Perruno', tipo_cocina='Tapas', direccion='C 3', admite_perros=True)

    def resena(self, resto, autor, nota):
        return Resena.objects.create(restaurante=resto, autor=autor.perfil, puntuacion=nota, titulo='t', texto='x')

    def test_paginas_publicas_y_para_ti_exige_sesion(self):
        for url in ('/descubre/novedades/', '/descubre/joyas/', '/descubre/ruleta/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.client.get('/descubre/para-ti/').status_code, 302)
        self.assertRedirects(self.client.get('/descubre/'), '/descubre/novedades/')
        self.entrar(self.ana)
        self.assertRedirects(self.client.get('/descubre/'), '/descubre/para-ti/')

    def test_para_ti_usa_lo_que_recomiendan_mis_seguidos_y_explica_por_que(self):
        self.resena(self.otro, self.bea, 5)
        self.entrar(self.ana)
        r = self.client.get('/descubre/para-ti/')
        self.assertEqual([x.id for x, _ in r.context['recomendados']], [self.otro.id])
        self.assertIn('Lo recomienda bea', r.context['recomendados'][0][1])
        self.assertContains(r, 'Lo recomienda bea')

    def test_no_recomienda_lo_ya_conocido_ni_lo_mal_valorado(self):
        self.resena(self.otro, self.bea, 5)
        self.resena(self.perro, self.bea, 2)  #2 estrellas: no es una recomendación
        for conocido in ('visita', 'guardado', 'resena'):
            if conocido == 'visita':
                Visita.objects.create(perfil=self.ana.perfil, restaurante=self.otro, fecha=date.today())
            elif conocido == 'guardado':
                Visita.objects.all().delete()
                Guardado.objects.create(perfil=self.ana.perfil, restaurante=self.otro)
            else:
                Guardado.objects.all().delete()
                self.resena(self.otro, self.ana, 4)
            self.entrar(self.ana)
            ids = [x.id for x, _ in self.client.get('/descubre/para-ti/').context['recomendados']]
            self.assertNotIn(self.otro.id, ids, conocido)
            self.assertNotIn(self.perro.id, ids)

    def test_respeta_preferencias_de_perro(self):
        self.resena(self.otro, self.bea, 5)    #no admite perros
        self.resena(self.perro, self.bea, 5)   #sí admite
        self.ana.perfil.lleva_perros = True
        self.ana.perfil.save()
        self.entrar(self.ana)
        ids = [x.id for x, _ in self.client.get('/descubre/para-ti/').context['recomendados']]
        self.assertEqual(ids, [self.perro.id])

    def test_sin_datos_cae_en_populares_de_su_ciudad(self):
        self.resena(self.otro, self.cai, 5)  #ana no sigue a cai
        self.entrar(self.ana)
        recomendados = self.client.get('/descubre/para-ti/').context['recomendados']
        self.assertEqual([x.id for x, _ in recomendados], [self.otro.id])
        self.assertTrue(recomendados[0][1][0].startswith('Popular'))

    def test_novedades_solo_con_fecha_de_alta_y_las_nuevas_primero(self):
        Restaurante.objects.filter(pk=self.resto.pk).update(fecha_alta=None)  #antiguo: no se sabe cuándo se añadió
        Restaurante.objects.filter(pk=self.otro.pk).update(fecha_alta=timezone.now() - timedelta(days=3))
        ids = [r.id for r in self.client.get('/descubre/novedades/').context['lista']]
        self.assertNotIn(self.resto.id, ids)
        self.assertEqual(ids[:2], [self.perro.id, self.otro.id])  #el recién creado antes que el de hace 3 días

    def test_joyas_exigen_varias_reseñas_y_nota_alta(self):
        self.resena(self.otro, self.ana, 5)            #una sola reseña: no basta
        self.resena(self.perro, self.ana, 5); self.resena(self.perro, self.bea, 5)       #2 reseñas, media 5: joya
        self.resena(self.resto, self.ana, 5); self.resena(self.resto, self.bea, 3)       #media 4: no llega a 4,5
        ids = [r.id for r in self.client.get('/descubre/joyas/').context['lista']]
        self.assertEqual(ids, [self.perro.id])

    def test_ruleta_exige_ciudad_y_respeta_filtros(self):
        r = self.client.get('/descubre/ruleta/', {'girar': 1})
        self.assertContains(r, 'Elige al menos una comunidad o una ciudad')
        self.assertIsNone(r.context['elegido'])
        r = self.client.get('/descubre/ruleta/', {'girar': 1, 'ciudad': self.ciudad.pk, 'perros': 1})
        self.assertEqual(r.context['elegido'].id, self.perro.id)  #el único que admite perros
        r = self.client.get('/descubre/ruleta/', {'girar': 1, 'ciudad': self.ciudad.pk, 'precio': 3})
        self.assertContains(r, 'No hay ningún restaurante')  #el precio desconocido no cuenta

    def test_ruleta_no_repite_el_anterior_y_no_visitados(self):
        for _ in range(15):
            r = self.client.get('/descubre/ruleta/', {'girar': 1, 'ciudad': self.ciudad.pk, 'excluir': self.resto.pk})
            self.assertNotEqual(r.context['elegido'].id, self.resto.id)
        Visita.objects.create(perfil=self.ana.perfil, restaurante=self.otro, fecha=date.today())
        Visita.objects.create(perfil=self.ana.perfil, restaurante=self.resto, fecha=date.today())
        self.entrar(self.ana)
        for _ in range(10):
            r = self.client.get('/descubre/ruleta/', {'girar': 1, 'ciudad': self.ciudad.pk, 'no_visitados': 1})
            self.assertEqual(r.context['elegido'].id, self.perro.id)

    def test_ruleta_entrada_con_ciudad_propia_y_parametros_basura(self):
        self.entrar(self.ana)
        self.assertEqual(self.client.get('/descubre/ruleta/').context['filtros'], {'ciudad': str(self.ciudad.pk)})
        for malo in ({'girar': 1, 'ciudad': 'abc'}, {'girar': 1, 'ciudad': self.ciudad.pk, 'excluir': 'x'}, {'girar': 1, 'comunidad': 'Nada'}):
            self.assertEqual(self.client.get('/descubre/ruleta/', malo).status_code, 200, malo)
