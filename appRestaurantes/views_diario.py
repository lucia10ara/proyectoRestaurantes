"""Mi diario, mi pasaporte y mis retos: solo los ve su dueño y se alimentan de las visitas confirmadas."""
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.shortcuts import render

from . import logros
from .models import Resena
from .views_social import perfil_o_403


@login_required
def diario(request):
    yo = perfil_o_403(request)
    visitas = Paginator(yo.visitas.select_related('restaurante__ciudad'), 30).get_page(request.GET.get('page'))
    #mi reseña de cada restaurante (si la hay) para enlazarla desde la visita
    mis_resenas = {}
    for r in Resena.objects.filter(autor=yo, restaurante_id__in=[v.restaurante_id for v in visitas]):
        mis_resenas.setdefault(r.restaurante_id, r)
    meses = []  #[(un día del mes, [visitas])] de más reciente a más antiguo
    for v in visitas:
        if not meses or (meses[-1][0].year, meses[-1][0].month) != (v.fecha.year, v.fecha.month):
            meses.append((v.fecha, []))
        v.mi_resena = mis_resenas.get(v.restaurante_id)
        meses[-1][1].append(v)
    return render(request, 'diario/diario.html', {'seccion': 'diario', 'meses': meses, 'lista': visitas, 'total': yo.visitas.count()})


@login_required
def pasaporte(request):
    e = logros.estadisticas(perfil_o_403(request))
    return render(request, 'diario/pasaporte.html', {'seccion': 'pasaporte', 'e': e})


@login_required
def mis_retos(request):
    e = logros.estadisticas(perfil_o_403(request))
    lista = logros.retos(e)
    return render(request, 'diario/retos.html', {'seccion': 'retos', 'retos': lista, 'hechos': sum(1 for r in lista if r['hecho'])})
