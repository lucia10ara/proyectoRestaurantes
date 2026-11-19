"""Planes entre amigos: quedar en un restaurante. Solo los ven quien lo crea y los invitados.
Invitar: solo a amigos (seguimiento mutuo). Responder: solo los invitados. Cancelar: solo quien lo creó."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import Http404
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import PlanForm
from .models import Plan, Invitacion, Restaurante
from .notificaciones import notificar
from .views import perfil_actual
from .views_social import perfil_o_403


def cuando_texto(plan):
    """'sábado 5/12 a las 21:30', en la hora de España."""
    c = timezone.localtime(plan.cuando)
    dias = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
    return f'{dias[c.weekday()]} {c.day}/{c.month} a las {c:%H:%M}'


def plan_visible(request, pk):
    plan = get_object_or_404(Plan.objects.select_related('creador__usuario', 'restaurante__ciudad'), pk=pk)
    if not plan.lo_ve(perfil_actual(request), request.user):
        raise Http404  #para quien no está invitado el plan no existe
    return plan


@login_required
def mis_planes(request):
    yo = perfil_o_403(request)
    ahora = timezone.now()
    suyos = Plan.objects.filter(Q(creador=yo) | Q(invitaciones__perfil=yo)).select_related('creador__usuario', 'restaurante__ciudad').distinct()
    pendientes = (Invitacion.objects.filter(perfil=yo, estado='pendiente', plan__cancelado=False, plan__cuando__gte=ahora)
                  .select_related('plan__creador__usuario', 'plan__restaurante__ciudad').order_by('plan__cuando'))
    return render(request, 'planes/mis_planes.html', {
        'pendientes': pendientes,
        'proximos': suyos.filter(cancelado=False, cuando__gte=ahora).order_by('cuando'),
        'pasados': suyos.filter(Q(cuando__lt=ahora) | Q(cancelado=True)).order_by('-cuando')[:20],
        'yo': yo,
    })


@login_required
def crear_plan(request, pk):
    restaurante = get_object_or_404(Restaurante.objects.select_related('ciudad'), pk=pk)
    yo = perfil_o_403(request)
    amigos = yo.amigos.select_related('usuario')
    form = PlanForm(request.POST or None, amigos=amigos)
    if not amigos.exists():
        messages.info(request, 'Para quedar con alguien, primero tenéis que seguiros mutuamente (ser amigos).')
        return redirect('detalle_restaurante', pk=pk)
    if form.is_valid():
        plan = Plan.objects.create(creador=yo, restaurante=restaurante, cuando=form.cleaned_data['cuando'],
                                   mensaje=form.cleaned_data['mensaje'].strip())
        for amigo in form.cleaned_data['invitados']:
            Invitacion.objects.create(plan=plan, perfil=amigo)
            notificar(amigo, yo, 'plan', f'{yo} te ha invitado a {restaurante.nombre} el {cuando_texto(plan)}.',
                      reverse('detalle_plan', args=[plan.pk]))
        messages.success(request, 'Plan creado. Les hemos avisado.')
        return redirect('detalle_plan', pk=plan.pk)
    return render(request, 'formulario.html', {
        'titulo': f'Quedar en {restaurante.nombre}', 'form': form, 'boton': 'Crear plan e invitar',
        'volver_texto': restaurante.nombre, 'volver_url': 'detalle_restaurante', 'volver_pk': pk})


def detalle_plan(request, pk):
    plan = plan_visible(request, pk)
    yo = perfil_actual(request)
    invitaciones = list(plan.invitaciones.select_related('perfil__usuario'))
    mi_invitacion = next((i for i in invitaciones if yo and i.perfil_id == yo.id), None)
    ya_paso = plan.cuando < timezone.now()
    van = [plan.creador] + [i.perfil for i in invitaciones if i.estado == 'si']
    return render(request, 'planes/detalle_plan.html', {
        'plan': plan, 'cuando': cuando_texto(plan), 'invitaciones': invitaciones, 'mi_invitacion': mi_invitacion,
        'ya_paso': ya_paso, 'es_creador': bool(yo) and yo.id == plan.creador_id,
        'puede_responder': bool(mi_invitacion) and not ya_paso and not plan.cancelado,
        'puede_confirmar_visita': bool(yo) and ya_paso and not plan.cancelado and yo in van,
        'fecha_plan': timezone.localtime(plan.cuando).date(),
        'van': len(van),
    })


@login_required
@require_POST
def responder_plan(request, pk):
    plan = plan_visible(request, pk)
    yo = perfil_o_403(request)
    invitacion = get_object_or_404(Invitacion, plan=plan, perfil=yo)  #solo los invitados responden
    respuesta = request.POST.get('respuesta')
    if respuesta not in ('si', 'no'):
        raise PermissionDenied
    if plan.cancelado or plan.cuando < timezone.now():
        messages.error(request, 'Este plan ya no admite respuestas.')
        return redirect('detalle_plan', pk=pk)
    if invitacion.estado != respuesta:
        invitacion.estado, invitacion.respondida = respuesta, timezone.now()
        invitacion.save(update_fields=['estado', 'respondida'])
        notificar(plan.creador, yo, 'plan',
                  f'{yo} {"irá" if respuesta == "si" else "no podrá ir"} a {plan.restaurante.nombre} el {cuando_texto(plan)}.',
                  reverse('detalle_plan', args=[pk]))
    messages.success(request, 'Respuesta guardada.')
    return redirect('detalle_plan', pk=pk)


@login_required
@require_POST
def cancelar_plan(request, pk):
    plan = plan_visible(request, pk)
    yo = perfil_o_403(request)
    if plan.creador_id != yo.id:
        raise PermissionDenied
    if not plan.cancelado:
        plan.cancelado = True
        plan.save(update_fields=['cancelado'])
        for inv in plan.invitaciones.exclude(estado='no').select_related('perfil'):
            notificar(inv.perfil, yo, 'plan', f'{yo} ha cancelado el plan de {plan.restaurante.nombre} del {cuando_texto(plan)}.',
                      reverse('detalle_plan', args=[pk]))
    messages.success(request, 'Plan cancelado. Les hemos avisado.')
    return redirect('detalle_plan', pk=pk)
