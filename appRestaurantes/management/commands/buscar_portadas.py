import json
import re
import time
import urllib.parse
import urllib.request
import urllib.robotparser
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import OperationalError

from appRestaurantes.models import Restaurante

PROGRESO = Path(settings.BASE_DIR) / 'portadas_progreso.json'  #ids de restaurantes ya intentados (con o sin éxito)
AGENTE = 'proyectoRestaurantes-universidad (vista previa de enlaces; trabajo de clase)'
MAX_BYTES = 300_000  #con la cabecera de la página basta para leer las etiquetas meta


class LectorMeta(HTMLParser):
    """Recoge la imagen de vista previa de una página (og:image o twitter:image) y para al terminar la cabecera."""
    def __init__(self):
        super().__init__()
        self.imagen = None

    def handle_starttag(self, tag, attrs):
        if tag != 'meta' or self.imagen:
            return
        a = {k.lower(): (v or '') for k, v in attrs}
        nombre = (a.get('property') or a.get('name')).lower() if (a.get('property') or a.get('name')) else ''
        if nombre in ('og:image', 'og:image:url', 'og:image:secure_url', 'twitter:image', 'twitter:image:src') and a.get('content'):
            self.imagen = a['content'].strip()

    def handle_endtag(self, tag):
        if tag == 'head':
            raise StopIteration  #ya no hace falta leer más


_robots = {}  #un robots.txt por dominio, guardado para no repetir la petición

def permitido(url):
    """Respeta el robots.txt de la web: si no nos deja entrar, no entramos."""
    partes = urllib.parse.urlsplit(url)
    base = f'{partes.scheme}://{partes.netloc}'
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            req = urllib.request.Request(base + '/robots.txt', headers={'User-Agent': AGENTE})
            with urllib.request.urlopen(req, timeout=6) as r:
                rp.parse(r.read(100_000).decode('utf-8', 'ignore').splitlines())
        except Exception:
            rp = None  #sin robots.txt accesible, se considera permitido
        _robots[base] = rp
    rp = _robots[base]
    return rp is None or rp.can_fetch(AGENTE, url)


def portada_de(web):
    """Devuelve el enlace a la imagen de portada de una web, o None si no se puede o no se debe."""
    try:
        if not permitido(web):
            return None
        req = urllib.request.Request(web, headers={'User-Agent': AGENTE, 'Accept': 'text/html'})
        with urllib.request.urlopen(req, timeout=8) as r:
            if 'html' not in r.headers.get('Content-Type', 'html'):
                return None
            html = r.read(MAX_BYTES).decode(r.headers.get_content_charset() or 'utf-8', 'ignore')
            final = r.geturl()
        lector = LectorMeta()
        try:
            lector.feed(html)
        except StopIteration:
            pass
        if not lector.imagen:
            return None
        url = urllib.parse.urljoin(final, lector.imagen)
        if not url.lower().startswith(('http://', 'https://')) or len(url) > 300:
            return None
        if urllib.parse.urlsplit(url).path.lower().endswith(('.svg', '.ico', '.gif')):  #logos e iconos, no fotos
            return None
        return url
    except Exception:
        return None  #web caída, lenta, con error de certificado... se salta


def web_de(restaurante):
    m = re.search(r'^Web: (https?://\S+)', restaurante.descripcion or '', re.M)
    return m.group(1) if m else None


class Command(BaseCommand):
    help = 'Busca la foto de portada (og:image) en la web propia de cada restaurante que tenga web y no tenga foto'

    def add_arguments(self, parser):
        parser.add_argument('--limite', type=int, help='Intentar como máximo N restaurantes (para probar)')
        parser.add_argument('--hilos', type=int, default=16, help='Webs consultadas a la vez (por defecto 16)')
        parser.add_argument('--reiniciar', action='store_true', help='Ignorar el progreso y volver a intentar todos')

    def handle(self, *args, **opts):
        hechos = set()
        if PROGRESO.exists() and not opts['reiniciar']:
            hechos = set(json.loads(PROGRESO.read_text(encoding='utf-8')))

        pendientes = [r for r in Restaurante.objects.filter(descripcion__contains='Web: http', foto_url__isnull=True, foto='')
                      .only('id', 'descripcion') if r.id not in hechos]
        if opts['limite']:
            pendientes = pendientes[:opts['limite']]
        self.stdout.write(f'{len(pendientes)} restaurantes con web y sin foto por intentar (Ctrl+C para parar, se retoma luego)')

        encontradas = intentadas = 0
        try:
            with ThreadPoolExecutor(max_workers=opts['hilos']) as pool:
                for i in range(0, len(pendientes), 200):  #de 200 en 200, guardando el progreso entre bloques
                    bloque = pendientes[i:i + 200]
                    for r, url in zip(bloque, pool.map(lambda r: portada_de(web_de(r)), bloque)):
                        intentadas += 1
                        hechos.add(r.id)
                        if url:
                            for intento in range(6):  #SQLite se bloquea si otra carga está escribiendo a la vez: se reintenta
                                try:
                                    Restaurante.objects.filter(pk=r.id, foto_url__isnull=True).update(foto_url=url)
                                    break
                                except OperationalError:
                                    time.sleep(3)
                            encontradas += 1
                    PROGRESO.write_text(json.dumps(sorted(hechos)), encoding='utf-8')
                    self.stdout.write(f'  {intentadas}/{len(pendientes)} intentadas, {encontradas} con foto')
        except KeyboardInterrupt:
            PROGRESO.write_text(json.dumps(sorted(hechos)), encoding='utf-8')
            self.stdout.write(self.style.WARNING('Parado. El progreso está guardado.'))
        self.stdout.write(self.style.SUCCESS(f'Hecho: {encontradas} restaurantes con foto de {intentadas} intentados'))
