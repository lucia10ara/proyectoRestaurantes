import json
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from appRestaurantes.models import Ciudad, Restaurante

# comunidades autonomas con su codigo ISO (se piden una a una porque España entera da timeout)
COMUNIDADES = {
    'Andalucía': 'ES-AN', 'Aragón': 'ES-AR', 'Asturias': 'ES-AS', 'Cantabria': 'ES-CB',
    'Castilla y León': 'ES-CL', 'Castilla-La Mancha': 'ES-CM', 'Canarias': 'ES-CN',
    'Cataluña': 'ES-CT', 'Extremadura': 'ES-EX', 'Galicia': 'ES-GA', 'Islas Baleares': 'ES-IB',
    'Murcia': 'ES-MC', 'Comunidad de Madrid': 'ES-MD', 'Navarra': 'ES-NC', 'País Vasco': 'ES-PV',
    'La Rioja': 'ES-RI', 'Comunidad Valenciana': 'ES-VC', 'Ceuta': 'ES-CE', 'Melilla': 'ES-ML',
}

# etiqueta cuisine de OpenStreetMap -> nombre en español
COCINAS = {
    'spanish': 'Española', 'regional': 'Regional', 'tapas': 'Tapas', 'pintxos': 'Pintxos',
    'italian': 'Italiano', 'pizza': 'Pizzería', 'pasta': 'Italiano', 'burger': 'Hamburguesería',
    'japanese': 'Japonés', 'sushi': 'Japonés', 'chinese': 'Chino', 'asian': 'Asiático',
    'indian': 'Indio', 'mexican': 'Mexicano', 'kebab': 'Kebab', 'turkish': 'Turco',
    'seafood': 'Marisquería', 'fish': 'Pescado', 'steak_house': 'Asador', 'grill': 'Parrilla',
    'chicken': 'Pollo', 'sandwich': 'Bocadillos', 'french': 'Francés', 'greek': 'Griego',
    'lebanese': 'Libanés', 'arab': 'Árabe', 'american': 'Americano', 'vegetarian': 'Vegetariano',
    'vegan': 'Vegano', 'mediterranean': 'Mediterráneo', 'peruvian': 'Peruano',
    'cider_house': 'Sidrería', 'basque': 'Vasco', 'burger_king': 'Hamburguesería', 'coffee_shop': 'Cafetería',
    'international': 'Internacional', 'regional;spanish': 'Regional', 'brazilian': 'Brasileño',
    'italian_pizza': 'Pizzería', 'ramen': 'Japonés', 'vietnamese': 'Vietnamita', 'moroccan': 'Marroquí',
    'argentinian': 'Argentino', 'thai': 'Tailandés', 'korean': 'Coreano', 'rice': 'Arrocería',
}

OVERPASS = 'https://overpass-api.de/api/interpreter'
PROGRESO = Path(settings.BASE_DIR) / 'carga_progreso.json'  #aquí se apuntan las comunidades ya terminadas


def consultar(consulta, intentos=5):
    """Lanza una consulta a Overpass; si el servidor está saturado (429/502/503/504) espera y reintenta."""
    datos = urllib.parse.urlencode({'data': consulta}).encode()
    req = urllib.request.Request(OVERPASS, data=datos, headers={'User-Agent': 'proyectoRestaurantes-universidad'})
    for i in range(intentos):
        try:
            with urllib.request.urlopen(req, timeout=330) as r:
                return json.load(r)['elements']
        except urllib.error.HTTPError as e:
            if e.code not in (429, 502, 503, 504) or i == intentos - 1:
                raise
            time.sleep(15 * (i + 1))


def pedir_overpass(codigo_iso, solo_fotos=False):
    """Descarga todos los restaurantes con nombre de una comunidad (o solo los que traen foto en OpenStreetMap)."""
    if solo_fotos:
        seleccion = ('(nwr["amenity"="restaurant"]["name"]["image"](area.a);'
                     'nwr["amenity"="restaurant"]["name"]["wikimedia_commons"](area.a););')
    else:
        seleccion = 'nwr["amenity"="restaurant"]["name"](area.a);'
    return consultar(
        '[out:json][timeout:300];'
        f'area["ISO3166-2"="{codigo_iso}"]->.a;'
        f'{seleccion}'
        'out center tags;'
    )


def foto_de(tags):
    """Enlace a una foto real del local si OpenStreetMap lo trae (etiquetas image o wikimedia_commons), si no None."""
    imagen = tags.get('image', '').strip()
    if imagen.lower().startswith(('http://', 'https://')) and len(imagen) <= 300:
        return imagen
    commons = tags.get('wikimedia_commons', '').strip()
    if commons.lower().startswith('file:'):  #las que empiezan por Category: no son una imagen concreta
        url = 'https://commons.wikimedia.org/wiki/Special:FilePath/' + urllib.parse.quote(commons[5:].replace(' ', '_')) + '?width=800'
        return url if len(url) <= 300 else None
    return None


def pedir_nucleos(codigo_iso):
    """Descarga ciudades, pueblos y aldeas de la comunidad (para asignar ciudad a los locales que no la traen)."""
    return consultar(
        '[out:json][timeout:300];'
        f'area["ISO3166-2"="{codigo_iso}"]->.a;'
        'node["place"~"^(city|town|village)$"]["name"](area.a);'
        'out;'
    )


class Nucleos:
    """Busca el núcleo de población más cercano a unas coordenadas (rejilla de 0,1 grados)."""
    CELDA = 0.1

    def __init__(self, elementos):
        self.rejilla = {}
        self.todos = []
        for n in elementos:
            if 'lat' in n and n.get('tags', {}).get('name'):
                item = (n['lat'], n['lon'], n['tags']['name'][:100])
                self.todos.append(item)
                self.rejilla.setdefault(self._celda(n['lat'], n['lon']), []).append(item)

    def _celda(self, lat, lon):
        return (int(lat // self.CELDA), int(lon // self.CELDA))

    def mas_cercano(self, lat, lon):
        cy, cx = self._celda(lat, lon)
        candidatos = []
        for r in range(1, 4):  # hasta ~30 km alrededor
            candidatos = [n for dy in range(-r, r + 1) for dx in range(-r, r + 1)
                          for n in self.rejilla.get((cy + dy, cx + dx), [])]
            if candidatos:
                break
        if not candidatos:
            return None
        # distancia aproximada (en la latitud de España 1º de longitud ≈ 0,77 de latitud)
        return min(candidatos, key=lambda n: (n[0] - lat) ** 2 + ((n[1] - lon) * 0.77) ** 2)[2]


def tipo_cocina(tags):
    for c in tags.get('cuisine', '').split(';'):
        c = c.strip().lower()
        if c in COCINAS:
            return COCINAS[c]
        if c:
            return c.replace('_', ' ').capitalize()
    return 'Restaurante'


def direccion(tags, el):
    calle = tags.get('addr:street', '')
    if calle:
        return f"{calle} {tags.get('addr:housenumber', '')}".strip()
    centro = el.get('center') or el
    # sin calle en OSM: usamos las coordenadas para no perder el local y mantener la unicidad
    return f"Coordenadas {centro['lat']:.5f}, {centro['lon']:.5f}"


def descripcion(tags):
    partes = []
    for clave, etiqueta in (('phone', 'Teléfono'), ('contact:phone', 'Teléfono'),
                            ('website', 'Web'), ('contact:website', 'Web'),
                            ('opening_hours', 'Horario')):
        if tags.get(clave) and not any(p.startswith(etiqueta) for p in partes):
            partes.append(f"{etiqueta}: {tags[clave]}")
    return '\n'.join(partes) or None


class Command(BaseCommand):
    help = 'Carga restaurantes de España desde OpenStreetMap (Overpass API)'

    def add_arguments(self, parser):
        parser.add_argument('--comunidad', help='Cargar solo una comunidad, p.ej. "País Vasco"')
        parser.add_argument('--limite', type=int, help='Máximo de restaurantes por comunidad (para probar)')
        parser.add_argument('--reiniciar', action='store_true', help='Ignorar el progreso guardado y empezar de cero')
        parser.add_argument('--solo-fotos', action='store_true',
                            help='Solo busca los restaurantes que traen foto en OpenStreetMap y se la pone a los que no tienen portada')

    def handle(self, *args, **opts):
        comunidades = COMUNIDADES
        if opts['comunidad']:
            if opts['comunidad'] not in COMUNIDADES:
                self.stderr.write('Comunidad no válida. Opciones: ' + ', '.join(COMUNIDADES))
                return
            comunidades = {opts['comunidad']: COMUNIDADES[opts['comunidad']]}

        # progreso: comunidades terminadas, para poder parar y retomar en otro momento
        # (con --limite es una prueba, así que ni se lee ni se guarda el progreso)
        usar_progreso = not opts['limite'] and not opts['comunidad'] and not opts['solo_fotos']
        if usar_progreso and not opts['reiniciar'] and PROGRESO.exists():
            hechas = set(json.loads(PROGRESO.read_text(encoding='utf-8')))
        else:
            hechas = set()

        for nombre_com, iso in comunidades.items():
            if nombre_com in hechas:
                self.stdout.write(f'{nombre_com}: ya cargada, se salta')
                continue
            self.stdout.write(f'{nombre_com}: descargando...')
            try:
                elementos = pedir_overpass(iso, opts['solo_fotos'])
            except Exception as e:  # si una comunidad falla seguimos con las demás
                self.stderr.write(f'  error en {nombre_com}: {e}')
                continue
            if opts['limite']:
                elementos = elementos[:opts['limite']]

            time.sleep(5)
            try:
                nucleos = Nucleos(pedir_nucleos(iso))
            except Exception as e:
                self.stderr.write(f'  no se pudieron descargar los núcleos de {nombre_com}: {e}')
                nucleos = Nucleos([])
                nucleos_ok = False  # sin núcleos se descartan muchos locales: esta comunidad no cuenta como terminada
            else:
                nucleos_ok = True

            ciudades = {c.nombre: c for c in Ciudad.objects.all()}
            vistos, nuevos, sin_ciudad, por_cercania = set(), [], 0, 0
            fotos = {}  #(ciudad, nombre, dirección) -> enlace a la foto real, para los que la traen
            for el in elementos:
                tags = el.get('tags', {})
                ciudad_nombre = (tags.get('addr:city') or tags.get('addr:municipality') or '').strip()[:100]
                centro = el.get('center') or el
                if not ciudad_nombre and 'lat' in centro:
                    ciudad_nombre = nucleos.mas_cercano(centro['lat'], centro['lon']) or ''
                    por_cercania += 1 if ciudad_nombre else 0
                if not ciudad_nombre or 'lat' not in centro:
                    sin_ciudad += 1
                    continue
                if ciudad_nombre not in ciudades:
                    ciudades[ciudad_nombre] = Ciudad.objects.get_or_create(
                        nombre=ciudad_nombre, defaults={'comunidad': nombre_com})[0]
                ciudad = ciudades[ciudad_nombre]
                nombre, dire = tags['name'][:100], direccion(tags, el)[:200]
                clave = (ciudad.id, nombre, dire)
                if clave in vistos:
                    continue
                vistos.add(clave)
                url_foto = foto_de(tags)
                if url_foto:
                    fotos[clave] = url_foto
                nuevos.append(Restaurante(
                    ciudad=ciudad, nombre=nombre, tipo_cocina=tipo_cocina(tags)[:50],
                    direccion=dire, descripcion=descripcion(tags), foto_url=url_foto,
                    latitud=centro['lat'], longitud=centro['lon'],  #los nuevos ya entran con su ubicación
                    admite_perros=tags.get('dog') in ('yes', 'leashed'),
                ))

            Restaurante.objects.bulk_create(nuevos, batch_size=1000, ignore_conflicts=True)

            #los que ya estaban cargados sin foto la reciben ahora (sin pisar una portada puesta a mano)
            con_foto = 0
            for (ciudad_id, nombre, dire), url_foto in fotos.items():
                con_foto += Restaurante.objects.filter(
                    ciudad_id=ciudad_id, nombre=nombre, direccion=dire, foto='', foto_url__isnull=True,
                ).update(foto_url=url_foto)
            if fotos:
                self.stdout.write(f'  {con_foto} restaurantes con foto real de OpenStreetMap')
            self.stdout.write(self.style.SUCCESS(
                f'  {len(nuevos)} procesados ({por_cercania} con ciudad asignada por cercanía), '
                f'{sin_ciudad} descartados por no tener ciudad'))
            if usar_progreso and nucleos_ok:
                hechas.add(nombre_com)
                PROGRESO.write_text(json.dumps(sorted(hechas), ensure_ascii=False), encoding='utf-8')
            time.sleep(10)  # pausa de cortesía con el servidor público

        if usar_progreso and len(hechas) == len(COMUNIDADES):
            self.stdout.write(self.style.SUCCESS('¡Todas las comunidades cargadas!'))
