from datetime import date, datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.utils import timezone
import calendar
from .models import Persona, OrdenTrabajo, Asignacion, ParteTrabajo, PartePersona, Equipo, Auditoria
from .forms import PersonaForm, OrdenTrabajoForm, AsignacionForm, LoginForm, QuickPersonaForm, ParteTrabajoForm, EquipoForm


def _auditar(request, accion, modelo, objeto_id, descripcion):
    if request.user.is_superuser:
        return
    persona_id = request.session.get('persona_id')
    persona = Persona.objects.filter(pk=persona_id).first() if persona_id else None
    Auditoria.objects.create(
        usuario=persona, accion=accion, modelo=modelo,
        objeto_id=objeto_id, descripcion=descripcion,
    )


def _mes_actual_range():
    hoy = timezone.now().date()
    inicio_mes = date(hoy.year, hoy.month, 1)
    ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
    fin_mes = date(hoy.year, hoy.month, ultimo_dia)
    return inicio_mes, fin_mes


def _periodos_anteriores():
    from itertools import chain
    rangos = set()
    for p in ParteTrabajo.objects.values_list('fecha_inicio', 'fecha_fin').distinct():
        rangos.add((p[0], p[1]))
    for a in Asignacion.objects.values_list('fecha', flat=True).distinct():
        inicio = date(a.year, a.month, 1)
        ultimo = calendar.monthrange(a.year, a.month)[1]
        fin = date(a.year, a.month, ultimo)
        rangos.add((inicio, fin))
    periodos = []
    for inicio, fin in rangos:
        total_acciones = (
            Asignacion.objects.filter(fecha__gte=inicio, fecha__lte=fin)
            .aggregate(t=Sum('acciones'))['t'] or 0
        ) + (
            ParteTrabajo.objects.filter(fecha_inicio__gte=inicio, fecha_fin__lte=fin)
            .aggregate(t=Sum('total_acciones'))['t'] or 0
        )
        periodos.append({
            'inicio': inicio,
            'fin': fin,
            'total_acciones': total_acciones,
        })
    periodos.sort(key=lambda x: x['fin'], reverse=True)
    return periodos


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

    fi = request.GET.get('fecha_inicio', '')
    ff = request.GET.get('fecha_fin', '')
    if fi and ff:
        try:
            inicio = datetime.strptime(fi, '%Y-%m-%d').date()
            fin = datetime.strptime(ff, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            inicio, fin = _mes_actual_range()
    else:
        inicio, fin = _mes_actual_range()

    personas = Persona.objects.filter(activo=True).annotate(
        total_act=Sum('asignaciones__acciones', filter=Q(
            asignaciones__fecha__gte=inicio, asignaciones__fecha__lte=fin,
        )),
        total_hd=Sum('asignaciones__horas_diurnas', filter=Q(
            asignaciones__fecha__gte=inicio, asignaciones__fecha__lte=fin,
        )),
        total_he=Sum('asignaciones__horas_extras', filter=Q(
            asignaciones__fecha__gte=inicio, asignaciones__fecha__lte=fin,
        )),
        partes_act=Sum('partes__parte__total_acciones', filter=Q(
            partes__parte__fecha_inicio__gte=inicio,
            partes__parte__fecha_fin__lte=fin,
        )),
        partes_hd=Sum('partes__horas_trabajadas', filter=Q(
            partes__parte__fecha_inicio__gte=inicio,
            partes__parte__fecha_fin__lte=fin,
        )),
        partes_he=Sum('partes__horas_extras', filter=Q(
            partes__parte__fecha_inicio__gte=inicio,
            partes__parte__fecha_fin__lte=fin,
        )),
    ).order_by('apellido', 'nombre')

    for p in personas:
        p.total_act = (p.total_act or 0) + (p.partes_act or 0)
        p.total_hd = (p.total_hd or 0) + (p.partes_hd or 0)
        p.total_he = (p.total_he or 0) + (p.partes_he or 0)
        p.total_horas = p.total_hd + p.total_he
        p.filtro_mes = f'{inicio:%d/%m/%Y} - {fin:%d/%m/%Y}'

    try:
        persona_actual = Persona.objects.get(pk=persona_id) if persona_id else None
    except Persona.DoesNotExist:
        persona_actual = None

    total_acciones_global = sum(p.total_act for p in personas)
    total_horas_global = sum(p.total_horas for p in personas)
    total_he_global = sum(p.total_he for p in personas)
    periodos = _periodos_anteriores()

    context = {
        'personas': personas,
        'persona_actual': persona_actual,
        'inicio': inicio,
        'fin': fin,
        'total_acciones_global': total_acciones_global,
        'total_horas_global': total_horas_global,
        'total_he_global': total_he_global,
        'periodos': periodos,
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
    desc = str(persona)
    if request.method == 'POST':
        form = PersonaForm(request.POST, instance=persona)
        if form.is_valid():
            form.save()
            _auditar(request, 'editar', 'Persona', persona.pk, desc)
            messages.success(request, 'Persona actualizada correctamente.')
            return redirect('persona_list')
    else:
        form = PersonaForm(instance=persona)
    return render(request, 'inventario/persona_form.html', {
        'form': form, 'accion': 'Editar', 'persona': persona
    })


def persona_delete(request, pk):
    persona = get_object_or_404(Persona, pk=pk)
    desc = str(persona)
    if request.method == 'POST':
        _auditar(request, 'eliminar', 'Persona', persona.pk, desc)
        persona.delete()
        messages.success(request, f'Persona "{desc}" eliminada correctamente.')
        return redirect('persona_list')
    return render(request, 'inventario/persona_confirm_delete.html', {'persona': persona})


def orden_list(request):
    query = request.GET.get('q', '')
    estado = request.GET.get('estado', '')
    f_persona = request.GET.get('persona', '')

    from itertools import chain

    ordenes_qs = OrdenTrabajo.objects.prefetch_related('asignaciones__persona').annotate(
        total_act=Sum('asignaciones__acciones'),
        total_pers=Count('asignaciones__persona', distinct=True),
    )
    if query:
        ordenes_qs = ordenes_qs.filter(
            Q(numero_orden__icontains=query) | Q(descripcion__icontains=query)
        )
    if estado == 'completada':
        ordenes_qs = ordenes_qs.filter(completada=True)
    elif estado == 'pendiente':
        ordenes_qs = ordenes_qs.filter(completada=False)
    if f_persona:
        ordenes_qs = ordenes_qs.filter(asignaciones__persona_id=f_persona)

    partes_qs = ParteTrabajo.objects.prefetch_related('personas__persona', 'creado_por')
    if query:
        partes_qs = partes_qs.filter(
            Q(total_acciones__icontains=query)
        )
    if f_persona:
        partes_qs = partes_qs.filter(personas__persona_id=f_persona)

    def orden_to_item(o):
        return {
            'tipo': 'orden',
            'pk': o.pk,
            'codigo': f'OT-{o.numero_orden}',
            'fecha': o.fecha,
            'descripcion': o.descripcion,
            'completada': o.completada,
            'total_pers': o.total_pers or 0,
            'total_act': o.total_act or 0,
            'personas_str': ', '.join(
                str(a.persona) for a in o.asignaciones.all()
            ),
        }

    def parte_to_item(p):
        personas_qs = p.personas.select_related('persona').all()
        personas_str = ', '.join(
            f'{pp.persona.apellido} {pp.persona.nombre}'
            for pp in personas_qs
        )
        fi = p.fecha_inicio.strftime('%d/%m/%Y')
        ff = p.fecha_fin.strftime('%d/%m/%Y')
        return {
            'tipo': 'parte',
            'pk': p.pk,
            'codigo': f'Parte #{p.pk}',
            'fecha': p.fecha_inicio,
            'descripcion': f'{fi} – {ff} ({p.acciones} acc × {p.cantidad_equipos} eq)',
            'completada': True,
            'total_pers': len(personas_qs),
            'total_act': p.total_acciones,
            'personas_str': personas_str,
        }

    items = sorted(
        chain(
            (orden_to_item(o) for o in ordenes_qs),
            (parte_to_item(p) for p in partes_qs),
        ),
        key=lambda x: x['fecha'],
        reverse=True,
    )

    paginator = Paginator(items, 20)
    page = request.GET.get('page', 1)
    items_page = paginator.get_page(page)

    personas = Persona.objects.filter(activo=True).order_by('apellido', 'nombre')

    return render(request, 'inventario/orden_list.html', {
        'items': items_page,
        'query': query,
        'estado': estado,
        'f_persona': f_persona,
        'personas': personas,
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
    desc = str(orden)
    if request.method == 'POST':
        form = OrdenTrabajoForm(request.POST, instance=orden)
        if form.is_valid():
            form.save()
            _auditar(request, 'editar', 'Orden de Trabajo', orden.pk, desc)
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
    desc = str(orden)
    if request.method == 'POST':
        _auditar(request, 'eliminar', 'Orden de Trabajo', orden.pk, desc)
        orden.delete()
        messages.success(request, f'{desc} eliminada correctamente.')
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
            return redirect('orden_list')
    else:
        form = ParteTrabajoForm(persona_inicial=persona_actual, fecha_min=fecha_min, fecha_max=fecha_max)

    return render(request, 'inventario/generar_orden.html', {
        'form': form,
        'persona_actual': persona_actual,
        'personas_iniciales': personas_iniciales,
        'fecha_min': fecha_min,
        'fecha_max': fecha_max,
    })


def parte_delete(request, pk):
    parte = get_object_or_404(ParteTrabajo, pk=pk)
    if request.method == 'POST':
        parte.delete()
        messages.success(request, 'Parte de trabajo eliminado correctamente.')
        return redirect('orden_list')
    return render(request, 'inventario/parte_confirm_delete.html', {'parte': parte})


def equipo_list(request):
    q = request.GET.get('q', '')
    f_marca = request.GET.get('marca', '')
    f_modelo = request.GET.get('modelo', '')
    f_unidad = request.GET.getlist('unidad')
    f_municipio = request.GET.get('municipio', '')
    f_estado = request.GET.get('estado', '')

    equipos = Equipo.objects.all()
    if q:
        equipos = equipos.filter(
            Q(marca__icontains=q) | Q(municipio__icontains=q) |
            Q(unidad_salud__icontains=q) | Q(denominacion__icontains=q) |
            Q(modelo__icontains=q) | Q(numero_serie__icontains=q)
        )
    if f_marca:
        equipos = equipos.filter(marca=f_marca)
    if f_modelo:
        equipos = equipos.filter(modelo=f_modelo)
    if f_unidad:
        equipos = equipos.filter(unidad_salud__in=f_unidad)
    if f_municipio:
        equipos = equipos.filter(municipio=f_municipio)
    if f_estado:
        equipos = equipos.filter(estado=f_estado)

    marcas = Equipo.objects.values_list('marca', flat=True).exclude(marca='').distinct().order_by('marca')
    modelos = Equipo.objects.values_list('modelo', flat=True).exclude(modelo='').distinct().order_by('modelo')
    unidades = Equipo.objects.values_list('unidad_salud', flat=True).exclude(unidad_salud='').distinct().order_by('unidad_salud')
    municipios_list = Equipo.objects.values_list('municipio', flat=True).exclude(municipio='').distinct().order_by('municipio')
    estados = Equipo.objects.values_list('estado', flat=True).exclude(estado='').distinct().order_by('estado')

    santiago = equipos.filter(municipio__icontains='Santiago').order_by('unidad_salud', 'denominacion')
    otros = equipos.exclude(municipio__icontains='Santiago').filter(municipio__gt='').order_by('municipio', 'unidad_salud')
    sin_municipio = equipos.filter(municipio='').order_by('unidad_salud')

    hospitales = {}
    for eq in santiago:
        hosp = eq.unidad_salud or 'Sin hospital'
        if hosp not in hospitales:
            hospitales[hosp] = []
        hospitales[hosp].append(eq)

    municipios_agrup = {}
    for eq in otros:
        mun = eq.municipio or 'Sin municipio'
        if mun not in municipios_agrup:
            municipios_agrup[mun] = []
        municipios_agrup[mun].append(eq)

    context = {
        'hospitales': hospitales,
        'municipios': municipios_agrup,
        'sin_municipio': sin_municipio,
        'marcas': marcas,
        'modelos': modelos,
        'unidades': unidades,
        'municipios_list': municipios_list,
        'estados': estados,
        'q': q,
        'f_marca': f_marca,
        'f_modelo': f_modelo,
        'f_unidad': f_unidad,
        'f_municipio': f_municipio,
        'f_unidad_str': ','.join(f_unidad),
        'f_estado': f_estado,
        'total': equipos.count(),
    }
    return render(request, 'inventario/equipo_list.html', context)


def equipo_create(request):
    if request.method == 'POST':
        form = EquipoForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Equipo creado.')
            return redirect('equipo_list')
    else:
        form = EquipoForm()
    estados = Equipo.objects.values_list('estado', flat=True).exclude(estado='').distinct().order_by('estado')
    return render(request, 'inventario/equipo_form.html', {'form': form, 'crear': True, 'estados': estados})


def equipo_update(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    desc = str(equipo)
    if request.method == 'POST':
        form = EquipoForm(request.POST, instance=equipo)
        if form.is_valid():
            form.save()
            _auditar(request, 'editar', 'Equipo', equipo.pk, desc)
            messages.success(request, 'Equipo actualizado.')
            return redirect('equipo_list')
    else:
        form = EquipoForm(instance=equipo)
    estados = Equipo.objects.values_list('estado', flat=True).exclude(estado='').distinct().order_by('estado')
    return render(request, 'inventario/equipo_form.html', {'form': form, 'crear': False, 'equipo': equipo, 'estados': estados})


def equipo_delete(request, pk):
    equipo = get_object_or_404(Equipo, pk=pk)
    desc = str(equipo)
    if request.method == 'POST':
        _auditar(request, 'eliminar', 'Equipo', equipo.pk, desc)
        equipo.delete()
        messages.success(request, 'Equipo eliminado.')
        return redirect('equipo_list')
    return render(request, 'inventario/equipo_confirm_delete.html', {'equipo': equipo})


def equipo_duplicados(request):
    from django.db.models import Count
    dups = Equipo.objects.values('numero_serie').exclude(numero_serie='').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')

    grupos = []
    for d in dups:
        equipos = Equipo.objects.filter(numero_serie=d['numero_serie'])
        grupos.append({
            'numero_serie': d['numero_serie'],
            'count': d['count'],
            'equipos': equipos,
        })

    return render(request, 'inventario/equipo_duplicados.html', {
        'grupos': grupos,
        'total_duplicados': len(grupos),
    })


def periodo_delete(request):
    if not request.user.is_authenticated:
        return redirect('login')
    fi = request.POST.get('fecha_inicio') or request.GET.get('fecha_inicio', '')
    ff = request.POST.get('fecha_fin') or request.GET.get('fecha_fin', '')
    if not fi or not ff:
        messages.error(request, 'Debes especificar un periodo.')
        return redirect('dashboard')
    try:
        inicio = datetime.strptime(fi, '%Y-%m-%d').date()
        fin = datetime.strptime(ff, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        messages.error(request, 'Fechas inválidas.')
        return redirect('dashboard')

    if request.method == 'POST':
        partes = ParteTrabajo.objects.filter(fecha_inicio__gte=inicio, fecha_fin__lte=fin)
        cant_partes = partes.count()
        partes.delete()

        asignaciones = Asignacion.objects.filter(fecha__gte=inicio, fecha__lte=fin)
        cant_asig = asignaciones.count()
        asignaciones.delete()

        OrdenTrabajo.objects.filter(~Q(asignaciones__pk__isnull=False)).delete()

        messages.success(
            request,
            f'Periodo {inicio:%d/%m/%Y} – {fin:%d/%m/%Y} eliminado: '
            f'{cant_partes} parte(s) y {cant_asig} asignacion(es).'
        )
        return redirect('dashboard')

    return render(request, 'inventario/periodo_confirm_delete.html', {
        'inicio': inicio,
        'fin': fin,
    })


def historial(request):
    if not request.user.is_authenticated:
        return redirect('login')
    logs = Auditoria.objects.select_related('usuario').all()
    paginator = Paginator(logs, 50)
    page = request.GET.get('page', 1)
    logs_page = paginator.get_page(page)
    return render(request, 'inventario/historial.html', {'logs': logs_page})


def historial_clear(request):
    if not request.user.is_superuser:
        return redirect('login')
    if request.method == 'POST':
        count = Auditoria.objects.count()
        Auditoria.objects.all().delete()
        messages.success(request, f'Historial limpiado ({count} registros eliminados).')
    return redirect('historial')
