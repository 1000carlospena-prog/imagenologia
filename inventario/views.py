from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.utils import timezone
from datetime import timedelta, datetime, date
import calendar
from .models import Persona, OrdenTrabajo, Asignacion, ParteTrabajo, PartePersona
from .forms import PersonaForm, OrdenTrabajoForm, AsignacionForm, LoginForm, QuickPersonaForm, ParteTrabajoForm


def _mes_actual_range():
    hoy = timezone.now().date()
    inicio_mes = date(hoy.year, hoy.month, 1)
    ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
    fin_mes = date(hoy.year, hoy.month, ultimo_dia)
    return inicio_mes, fin_mes


def _mes_pasado_a_mes_actual_range():
    hoy = timezone.now().date()
    if hoy.month == 1:
        mes_pasado_inicio = date(hoy.year - 1, 12, 1)
    else:
        mes_pasado_inicio = date(hoy.year, hoy.month - 1, 1)
    ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
    fin_mes_actual = date(hoy.year, hoy.month, ultimo_dia)
    return mes_pasado_inicio, fin_mes_actual


def login_view(request):
    if request.user.is_authenticated:
        return redirect('select_persona')
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request, user)
            messages.success(request, f'Bienvenido, {user.username}.')
            return redirect('select_persona')
    else:
        form = LoginForm()
    return render(request, 'inventario/login.html', {'form': form})


def logout_view(request):
    auth_logout(request)
    if 'persona_id' in request.session:
        del request.session['persona_id']
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('login')


def select_persona(request):
    if not request.user.is_authenticated:
        return redirect('login')
    if request.method == 'POST':
        if 'persona_id' in request.POST:
            persona_id = request.POST.get('persona_id')
            try:
                persona = Persona.objects.get(pk=persona_id, activo=True)
                request.session['persona_id'] = persona.pk
                request.session['persona_nombre'] = str(persona)
                messages.success(request, f'Has iniciado sesión como {persona}.')
                return redirect('dashboard')
            except Persona.DoesNotExist:
                messages.error(request, 'Persona no encontrada.')
                return redirect('select_persona')
        elif 'nombre' in request.POST:
            form = QuickPersonaForm(request.POST)
            if form.is_valid():
                persona = form.save(commit=False)
                persona.apellido = persona.nombre 
                persona.activo = True
                persona.save()
                messages.success(request, f'Persona "{persona.nombre}" creada. Selecciónala para iniciar.')
                return redirect('select_persona')
            else:
                personas = Persona.objects.filter(activo=True).order_by('apellido', 'nombre')
                return render(request, 'inventario/select_persona.html', {
                    'personas': personas,
                    'form': form,
                })
        return redirect('select_persona')
    personas = Persona.objects.filter(activo=True).order_by('apellido', 'nombre')
    form = QuickPersonaForm()
    return render(request, 'inventario/select_persona.html', {
        'personas': personas,
        'form': form,
    })


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect('login')
    persona_id = request.session.get('persona_id')
    inicio_mes, fin_mes = _mes_actual_range()

    personas = Persona.objects.filter(activo=True).annotate(
        total_act=Sum('asignaciones__acciones'),
        total_hd=Sum('asignaciones__horas_diurnas'),
        total_he=Sum('asignaciones__horas_extras'),
        partes_act=Sum('partes__parte__total_acciones', filter=Q(
            partes__parte__fecha_inicio__gte=inicio_mes,
            partes__parte__fecha_fin__lte=fin_mes,
        )),
        partes_hd=Sum('partes__horas_trabajadas', filter=Q(
            partes__parte__fecha_inicio__gte=inicio_mes,
            partes__parte__fecha_fin__lte=fin_mes,
        )),
        partes_he=Sum('partes__horas_extras', filter=Q(
            partes__parte__fecha_inicio__gte=inicio_mes,
            partes__parte__fecha_fin__lte=fin_mes,
        )),
    ).order_by('apellido', 'nombre')

    for p in personas:
        p.total_act = (p.total_act or 0) + (p.partes_act or 0)
        p.total_hd = (p.total_hd or 0) + (p.partes_hd or 0)
        p.total_he = (p.total_he or 0) + (p.partes_he or 0)
        p.total_horas = p.total_hd + p.total_he
        p.filtro_mes = f'{inicio_mes:%d/%m/%Y} - {fin_mes:%d/%m/%Y}'

    try:
        persona_actual = Persona.objects.get(pk=persona_id) if persona_id else None
    except Persona.DoesNotExist:
        persona_actual = None

    total_acciones_global = sum(p.total_act for p in personas)
    total_horas_global = sum(p.total_horas for p in personas)
    total_he_global = sum(p.total_he for p in personas)

    context = {
        'personas': personas,
        'persona_actual': persona_actual,
        'inicio_mes': inicio_mes,
        'fin_mes': fin_mes,
        'total_acciones_global': total_acciones_global,
        'total_horas_global': total_horas_global,
        'total_he_global': total_he_global,
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


def generar_orden(request):
    if not request.user.is_authenticated:
        return redirect('login')
    persona_id = request.session.get('persona_id')
    try:
        persona_actual = Persona.objects.get(pk=persona_id) if persona_id else None
    except Persona.DoesNotExist:
        persona_actual = None

    hoy = timezone.now().date()
    fecha_max = date(hoy.year, hoy.month, calendar.monthrange(hoy.year, hoy.month)[1])
    if hoy.month == 1:
        fecha_min = date(hoy.year - 1, 12, 1)
    else:
        fecha_min = date(hoy.year, hoy.month - 1, 1)

    personas_iniciales = [persona_actual.pk] if persona_actual else []

    if request.method == 'POST':
        posted_pks = [int(pk) for pk in request.POST.getlist('personas')]
        if posted_pks:
            personas_iniciales = posted_pks
        form = ParteTrabajoForm(request.POST, persona_inicial=persona_actual, fecha_min=fecha_min, fecha_max=fecha_max)
        if form.is_valid():
            parte = form.save(commit=False)
            parte.creado_por = persona_actual
            parte.save()

            personas_seleccionadas = form.cleaned_data['personas']
            errores = []
            for p in personas_seleccionadas:
                conflictos = PartePersona.objects.filter(
                    persona=p,
                ).exclude(
                    parte=parte
                ).filter(
                    Q(parte__fecha_inicio__lte=parte.fecha_fin) &
                    Q(parte__fecha_fin__gte=parte.fecha_inicio)
                )
                if conflictos.exists():
                    errores.append(
                        f'{p} ya está asignado a otro parte de trabajo en el periodo '
                        f'{parte.fecha_inicio} - {parte.fecha_fin}'
                    )

            if errores:
                parte.delete()
                for error in errores:
                    messages.error(request, error)
                personas_qs = Persona.objects.filter(activo=True)
                form.fields['personas'].queryset = personas_qs
                return render(request, 'inventario/generar_orden.html', {
                    'form': form,
                    'persona_actual': persona_actual,
                    'personas_iniciales': personas_iniciales,
                    'fecha_min': fecha_min,
                    'fecha_max': fecha_max,
                })

            horas_trabajadas = form.cleaned_data.get('horas_trabajadas') or 0
            horas_extras = form.cleaned_data.get('horas_extras') or 0

            for p in personas_seleccionadas:
                PartePersona.objects.create(
                    parte=parte,
                    persona=p,
                    horas_trabajadas=horas_trabajadas,
                    horas_extras=horas_extras,
                )

            messages.success(request, 'Parte de trabajo creado correctamente.')
            return redirect('dashboard')
    else:
        form = ParteTrabajoForm(persona_inicial=persona_actual, fecha_min=fecha_min, fecha_max=fecha_max)

    return render(request, 'inventario/generar_orden.html', {
        'form': form,
        'persona_actual': persona_actual,
        'personas_iniciales': personas_iniciales,
        'fecha_min': fecha_min,
        'fecha_max': fecha_max,
    })
