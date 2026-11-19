"""Pasaporte de sellos y retos. Todo se calcula al momento a partir de las VISITAS CONFIRMADAS del propio usuario
(guardar, mirar o subir una foto no cuentan). No se guarda nada: si borra una visita, desaparece su sello."""
from datetime import date

from .models import Ciudad, Resena, Visita, categoria_cocina

#nombre legible de cada categoría de cocina (las claves son las de categoria_cocina; 'generica' no da sello)
COCINAS = {
    'tapas': 'Tapas y cocina española', 'pizza': 'Pizza', 'pasta': 'Italiana y pasta', 'sushi': 'Japonesa y coreana',
    'asiatica': 'Asiática', 'mexicana': 'Latina', 'kebab': 'Kebab y Oriente', 'marisco': 'Marisco y pescado',
    'carne': 'Carnes y asador', 'arroz': 'Arroces', 'hamburguesa': 'Hamburguesas', 'bocadillo': 'Bocadillos',
    'cafe': 'Cafeterías', 'vegetariano': 'Vegetariana',
}


def estadisticas(perfil, hoy=None):
    """Todo lo que necesitan el pasaporte y los retos."""
    hoy = hoy or date.today()
    visitas = list(perfil.visitas.select_related('restaurante__ciudad').order_by('fecha', 'id'))

    restaurantes, ciudades, comunidades, cocinas = {}, {}, {}, {}
    for v in visitas:
        r = v.restaurante
        restaurantes.setdefault(r.id, []).append(v.fecha)  #días en que fue a cada restaurante
        c = ciudades.setdefault(r.ciudad_id, {'ciudad': r.ciudad, 'primera': v.fecha, 'restaurantes': set()})
        c['restaurantes'].add(r.id)
        if r.ciudad.comunidad:
            comunidades.setdefault(r.ciudad.comunidad, {'nombre': r.ciudad.comunidad, 'primera': v.fecha, 'ciudades': set()})['ciudades'].add(r.ciudad_id)
        clave = categoria_cocina(r.tipo_cocina)
        if clave in COCINAS:
            cocinas.setdefault(clave, {'clave': clave, 'nombre': COCINAS[clave], 'primera': v.fecha, 'restaurantes': set()})['restaurantes'].add(r.id)

    return {
        'visitas': visitas,
        'total_visitas': len(visitas),
        'n_restaurantes': len(restaurantes),
        'ciudades': sorted(ciudades.values(), key=lambda c: c['primera']),
        'comunidades': sorted(comunidades.values(), key=lambda c: c['primera']),
        'cocinas': sorted(cocinas.values(), key=lambda c: c['primera']),
        'posibles_comunidades': Ciudad.objects.exclude(comunidad__isnull=True).exclude(comunidad='').values('comunidad').distinct().count(),
        'posibles_cocinas': len(COCINAS),
        'visitas_este_mes': sum(1 for v in visitas if (v.fecha.year, v.fecha.month) == (hoy.year, hoy.month)),
        'max_mismo_sitio': max((len(set(dias)) for dias in restaurantes.values()), default=0),
        'n_resenas': Resena.objects.filter(autor=perfil).count(),
    }


#(nombre, qué hay que hacer, objetivo, campo de estadisticas que se mide)
RETOS = [
    ('Primer sitio', 'Confirma tu primera visita a un restaurante.', 1, lambda e: e['n_restaurantes']),
    ('Diez sitios', 'Visita 10 restaurantes distintos.', 10, lambda e: e['n_restaurantes']),
    ('Veinticinco sitios', 'Visita 25 restaurantes distintos.', 25, lambda e: e['n_restaurantes']),
    ('Trotamundos', 'Come en 3 ciudades distintas.', 3, lambda e: len(e['ciudades'])),
    ('Cambio de aires', 'Come en 2 comunidades autónomas distintas.', 2, lambda e: len(e['comunidades'])),
    ('Paladar curioso', 'Prueba 5 tipos de cocina distintos.', 5, lambda e: len(e['cocinas'])),
    ('Sin fronteras', 'Prueba 10 tipos de cocina distintos.', 10, lambda e: len(e['cocinas'])),
    ('Mes goloso', 'Haz 4 visitas en este mes.', 4, lambda e: e['visitas_este_mes']),
    ('Cliente fijo', 'Vuelve a un mismo restaurante en 3 días distintos.', 3, lambda e: e['max_mismo_sitio']),
    ('Crítico gastronómico', 'Escribe 5 reseñas.', 5, lambda e: e['n_resenas']),
]


def retos(e):
    lista = []
    for nombre, descripcion, objetivo, medir in RETOS:
        actual = medir(e)
        lista.append({'nombre': nombre, 'descripcion': descripcion, 'objetivo': objetivo, 'actual': min(actual, objetivo),
                      'hecho': actual >= objetivo, 'porcentaje': round(min(actual, objetivo) / objetivo * 100)})
    return lista
