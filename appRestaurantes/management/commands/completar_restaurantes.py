import json
import re
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from appRestaurantes.models import Restaurante
from .cargar_restaurantes import COMUNIDADES, consultar, direccion

PROGRESO = Path(settings.BASE_DIR) / 'completar_progreso.json'  #comunidades ya completadas
CAMPOS = ['latitud', 'longitud', 'terraza', 'vegetariano', 'vegano', 'accesible']


def si_no(valor):
    """Etiqueta de OpenStreetMap -> True / False / None (None = no lo sabemos, no se rellena)."""
    valor = (valor or '').strip().lower()
    if valor in ('yes', 'only', 'designated'):
        return True
    if valor == 'no':
        return False
    return None


def datos_de(tags, el):
    centro = el.get('center') or el
    return {
        'latitud': centro.get('lat'),
        'longitud': centro.get('lon'),
        'terraza': si_no(tags.get('outdoor_seating')),
        'vegetariano': si_no(tags.get('diet:vegetarian')),
        'vegano': si_no(tags.get('diet:vegan')),
        'accesible': si_no(tags.get('wheelchair')),  #'limited' se queda como desconocido
    }


class Command(BaseCommand):
    help = ('Completa los restaurantes ya cargados con coordenadas y datos de OpenStreetMap '
            '(terraza, vegetariano, vegano, accesible). Solo rellena lo que está vacío.')

    def add_arguments(self, parser):
        parser.add_argument('--comunidad', help='Completar solo una comunidad, p.ej. "País Vasco"')
        parser.add_argument('--reiniciar', action='store_true', help='Ignorar el progreso guardado')

    def handle(self, *args, **opts):
        # 1) los que se guardaron sin calle tienen las coordenadas en la dirección: se aprovechan sin descargar nada
        por_direccion = []
        for r in Restaurante.objects.filter(latitud__isnull=True, direccion__startswith='Coordenadas').only('id', 'direccion'):
            m = re.match(r'Coordenadas (-?\d+\.\d+), (-?\d+\.\d+)', r.direccion)
            if m:
                r.latitud, r.longitud = float(m.group(1)), float(m.group(2))
                por_direccion.append(r)
        Restaurante.objects.bulk_update(por_direccion, ['latitud', 'longitud'], batch_size=1000)
        self.stdout.write(f'{len(por_direccion)} restaurantes con coordenadas sacadas de su dirección')

        # 2) el resto, comunidad a comunidad desde OpenStreetMap
        comunidades = COMUNIDADES
        if opts['comunidad']:
            if opts['comunidad'] not in COMUNIDADES:
                self.stderr.write('Comunidad no válida. Opciones: ' + ', '.join(COMUNIDADES))
                return
            comunidades = {opts['comunidad']: COMUNIDADES[opts['comunidad']]}
        usar_progreso = not opts['comunidad']
        hechas = set(json.loads(PROGRESO.read_text(encoding='utf-8'))) if (usar_progreso and PROGRESO.exists() and not opts['reiniciar']) else set()

        for nombre_com, iso in comunidades.items():
            if nombre_com in hechas:
                self.stdout.write(f'{nombre_com}: ya completada, se salta')
                continue
            self.stdout.write(f'{nombre_com}: descargando...')
            try:
                elementos = consultar(
                    '[out:json][timeout:300];'
                    f'area["ISO3166-2"="{iso}"]->.a;'
                    'nwr["amenity"="restaurant"]["name"](area.a);'
                    'out center tags;'
                )
            except Exception as e:
                self.stderr.write(f'  error en {nombre_com}: {e}')
                continue

            #índice de los restaurantes de esa comunidad: (nombre, dirección) -> [restaurantes]
            indice = {}
            for r in Restaurante.objects.filter(ciudad__comunidad=nombre_com).select_related('ciudad').only(
                    'id', 'nombre', 'direccion', 'ciudad__nombre', *CAMPOS):
                indice.setdefault((r.nombre, r.direccion), []).append(r)

            cambiados, ambiguos = {}, 0
            for el in elementos:
                tags = el.get('tags', {})
                if not (el.get('center') or 'lat' in el):
                    continue
                candidatos = indice.get((tags['name'][:100], direccion(tags, el)[:200]), [])
                if len(candidatos) > 1:  #mismo nombre y calle en dos ciudades: se decide por la ciudad de OSM
                    ciudad_osm = (tags.get('addr:city') or '').strip()
                    candidatos = [c for c in candidatos if c.ciudad.nombre == ciudad_osm]
                if len(candidatos) != 1:
                    ambiguos += 1 if candidatos else 0
                    continue
                r = candidatos[0]
                for campo, valor in datos_de(tags, el).items():
                    if valor is not None and getattr(r, campo) is None:  #nunca se pisa un dato que ya existe
                        setattr(r, campo, valor)
                        cambiados[r.id] = r

            Restaurante.objects.bulk_update(list(cambiados.values()), CAMPOS, batch_size=500)
            self.stdout.write(self.style.SUCCESS(f'  {len(cambiados)} restaurantes completados ({ambiguos} sin decidir)'))
            if usar_progreso:
                hechas.add(nombre_com)
                PROGRESO.write_text(json.dumps(sorted(hechas), ensure_ascii=False), encoding='utf-8')
            time.sleep(10)  #pausa de cortesía con el servidor público

        con = Restaurante.objects.filter(latitud__isnull=False).count()
        self.stdout.write(self.style.SUCCESS(f'Restaurantes con ubicación: {con} de {Restaurante.objects.count()}'))
