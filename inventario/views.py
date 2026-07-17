from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta
from .models import Persona, OrdenTrabajo, Asignacion
from .forms import PersonaForm, OrdenTrabajoForm, AsignacionForm


def dashboard(request):
    total_personas = Persona.objects.count()
    personas_activas = Persona.objects.filter(activo=True).count()
    total_ordenes = OrdenTrabajo.objects.count()
    ordenes_completadas = OrdenTrabajo.objects.filter(completada=True).count()
    ordenes_pendientes = OrdenTrabajo.objects.filter(completada=False).count()

    stats_asignaciones = Asignacion.objects.aggregate(
        total_acciones=Sum('acciones'),
        total_horas_diurnas=Sum('horas_diurnas'),
        total_horas_extras=Sum('horas_extras'),
    )

    ultimas_ordenes = OrdenTrabajo.objects.select_related().prefetch_related('asignaciones').order_by('-fecha_creacion')[:5]

    top_personas = Persona.objects.filter(activo=True).annotate(
        total_act=Sum('asignaciones__acciones'),
        total_hd=Sum('asignaciones__horas_diurnas'),
        total_he=Sum('asignaciones__horas_extras'),
    ).order_by('-total_act')[:10]

    acciones_por_mes = (
        Asignacion.objects
        .values('fecha__year', 'fecha__month')
        .annotate(
            total_acciones=Sum('acciones'),
            total_horas=Sum('horas_diurnas') + Sum('horas_extras'),
        )
        .order_by('-fecha__year', '-fecha__month')[:12]
    )

    for p in top_personas:
        p.total_act = p.total_act or 0
        p.total_hd = p.total_hd or 0
        p.total_he = p.total_he or 0

    context = {
        'total_personas': total_personas,
        'personas_activas': personas_activas,
        'total_ordenes': total_ordenes,
        'ordenes_completadas': ordenes_completadas,
        'ordenes_pendientes': ordenes_pendientes,
        'total_acciones': stats_asignaciones['total_acciones'] or 0,
        'total_horas_diurnas': stats_asignaciones['total_horas_diurnas'] or 0,
        'total_horas_extras': stats_asignaciones['total_horas_extras'] or 0,
        'ultimas_ordenes': ultimas_ordenes,
        'top_personas': top_personas,
        'acciones_por_mes': list(acciones_por_mes),
    }
    return render(request, 'inventario/dashboard.html', context)


def persona_list(request):
    query = request.GET.get('q', '')
    personas = Persona.objects.all()
    if query:
        personas = personas.filter(
            Q(nombre__icontains=query) | Q(apellido__icontains=query) |
            Q(email__icontains=query) | Q(telefono__icontains=query)
        )
    personas = personas.annotate(
        total_act=Sum('asignaciones__acciones'),
        total_hd=Sum('asignaciones__horas_diurnas'),
        total_he=Sum('asignaciones__horas_extras'),
    ).order_by('apellido', 'nombre')

    paginator = Paginator(personas, 20)
    page = request.GET.get('page', 1)
    personas_page = paginator.get_page(page)

    return render(request, 'inventario/persona_list.html', {
        'personas': personas_page,
        'query': query,
    })


def persona_create(request):
    if request.method == 'POST':
        form = PersonaForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Persona registrada correctamente.')
            return redirect('persona_list')
    else:
        form = PersonaForm()
    return render(request, 'inventario/persona_form.html', {'form': form, 'accion': 'Registrar'})


def persona_update(request, pk):
    persona = get_object_or_404(Persona, pk=pk)
    if request.method == 'POST':
        form = PersonaForm(request.POST, instance=persona)
        if form.is_valid():
            form.save()
            messages.success(request, 'Persona actualizada correctamente.')
            return redirect('persona_list')
    else:
        form = PersonaForm(instance=persona)
    return render(request, 'inventario/persona_form.html', {
        'form': form, 'accion': 'Editar', 'persona': persona
    })


def persona_delete(request, pk):
    persona = get_object_or_404(Persona, pk=pk)
    if request.method == 'POST':
        nombre = str(persona)
        persona.delete()
        messages.success(request, f'Persona "{nombre}" eliminada correctamente.')
        return redirect('persona_list')
    return render(request, 'inventario/persona_confirm_delete.html', {'persona': persona})


def orden_list(request):
    query = request.GET.get('q', '')
    estado = request.GET.get('estado', '')
    ordenes = OrdenTrabajo.objects.all()

    if query:
        ordenes = ordenes.filter(
            Q(numero_orden__icontains=query) | Q(descripcion__icontains=query)
        )
    if estado == 'completada':
        ordenes = ordenes.filter(completada=True)
    elif estado == 'pendiente':
        ordenes = ordenes.filter(completada=False)

    ordenes = ordenes.annotate(
        total_act=Sum('asignaciones__acciones'),
        total_pers=Count('asignaciones__persona', distinct=True),
    ).order_by('-fecha', '-fecha_creacion')

    paginator = Paginator(ordenes, 20)
    page = request.GET.get('page', 1)
    ordenes_page = paginator.get_page(page)

    return render(request, 'inventario/orden_list.html', {
        'ordenes': ordenes_page,
        'query': query,
        'estado': estado,
    })


def orden_create(request):
    if request.method == 'POST':
        form = OrdenTrabajoForm(request.POST)
        if form.is_valid():
            orden = form.save()
            messages.success(request, f'Orden de Trabajo OT-{orden.numero_orden} creada correctamente.')
            return redirect('orden_detail', pk=orden.pk)
    else:
        form = OrdenTrabajoForm()
    return render(request, 'inventario/orden_form.html', {'form': form, 'accion': 'Crear'})


def orden_update(request, pk):
    orden = get_object_or_404(OrdenTrabajo, pk=pk)
    if request.method == 'POST':
        form = OrdenTrabajoForm(request.POST, instance=orden)
        if form.is_valid():
            form.save()
            messages.success(request, 'Orden de Trabajo actualizada correctamente.')
            return redirect('orden_detail', pk=orden.pk)
    else:
        form = OrdenTrabajoForm(instance=orden)
    return render(request, 'inventario/orden_form.html', {
        'form': form, 'accion': 'Editar', 'orden': orden
    })


def orden_detail(request, pk):
    orden = get_object_or_404(
        OrdenTrabajo.objects.prefetch_related(
            'asignaciones__persona'
        ), pk=pk
    )
    asignaciones = orden.asignaciones.select_related('persona').all()

    if request.method == 'POST':
        form = AsignacionForm(request.POST)
        if form.is_valid():
            asignacion = form.save(commit=False)
            asignacion.orden_trabajo = orden
            asignacion.save()
            messages.success(request, f'{asignacion.persona} agregado a la orden correctamente.')
            return redirect('orden_detail', pk=orden.pk)
    else:
        form = AsignacionForm()

    totales = asignaciones.aggregate(
        total_acciones=Sum('acciones'),
        total_hd=Sum('horas_diurnas'),
        total_he=Sum('horas_extras'),
    )

    context = {
        'orden': orden,
        'asignaciones': asignaciones,
        'form': form,
        'total_acciones': totales['total_acciones'] or 0,
        'total_hd': totales['total_hd'] or 0,
        'total_he': totales['total_he'] or 0,
    }
    return render(request, 'inventario/orden_detail.html', context)


def orden_delete(request, pk):
    orden = get_object_or_404(OrdenTrabajo, pk=pk)
    if request.method == 'POST':
        num = orden.numero_orden
        orden.delete()
        messages.success(request, f'Orden de Trabajo OT-{num} eliminada correctamente.')
        return redirect('orden_list')
    return render(request, 'inventario/orden_confirm_delete.html', {'orden': orden})


def asignacion_delete(request, pk):
    asignacion = get_object_or_404(Asignacion, pk=pk)
    orden_pk = asignacion.orden_trabajo.pk
    if request.method == 'POST':
        asignacion.delete()
        messages.success(request, 'Asignación eliminada correctamente.')
        return redirect('orden_detail', pk=orden_pk)
    return render(request, 'inventario/asignacion_confirm_delete.html', {'asignacion': asignacion})
