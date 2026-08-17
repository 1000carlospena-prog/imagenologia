from datetime import date, datetime
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.hashers import check_password, make_password
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.clickjacking import xframe_options_sameorigin
import calendar
import uuid
from .models import (
    Configuracion, get_configuracion, Departamento, Persona, OrdenTrabajo, Asignacion,
    ParteTrabajo, PartePersona, Equipo, Auditoria, Periodo, VisitaLink, Centro, Municipio,
    SolicitudEquipo, CambioPendiente, DepartamentoCentro, CAMPO_SNAPSHOT,
    centro_provincial_por_defecto,
)
from .forms import (
    PersonaForm, OrdenTrabajoForm, AsignacionForm, LoginForm, LoginDepartamentoForm,
    LoginCentroForm, ConfiguracionContrasenaForm, QuickPersonaForm, ParteTrabajoForm,
    EquipoForm, CrearDepartamentoForm, SolicitudEquipoForm, CentroForm, MunicipioForm,
    DepartamentoEditarForm, DepartamentoContrasenaForm, DepartamentoCentroForm,
)


def _auditar(request, accion, modelo, objeto_id, descripcion):
    if request.user.is_superuser:
        return
    persona_id = request.session.get('persona_id')
    persona = Persona.objects.filter(pk=persona_id).first() if persona_id else None
    Auditoria.objects.create(
        usuario=persona, accion=accion, modelo=modelo,
        objeto_id=objeto_id, descripcion=descripcion,
    )


def _tiene_sesion(request):
    return bool(
        request.user.is_authenticated
        or request.session.get('is_visitor')
        or request.session.get('departamento_pk')
    )


def _departamento_sesion(request):
    pk = request.session.get('departamento_pk')
    if not pk:
        return None
    try:
        return Departamento.objects.get(pk=pk)
    except Departamento.DoesNotExist:
        request.session.pop('departamento_pk', None)
        return None


def alcanzar_departamentos(request):
    """Departamentos alcanzables según el rol/sesión (P2-D2):
    staff/visitante -> todos; territorial -> los del CENTRO PADRE (sus
    departamentos son los del padre, con contraseñas locales propias);
    departamento restringido -> solo el suyo; global -> todos."""
    if request.user.is_staff:
        return Departamento.objects.all()
    if request.session.get('is_visitor'):
        return Departamento.objects.all()
    depto = _departamento_sesion(request)
    if depto and depto.restringido:
        return Departamento.objects.filter(pk=depto.pk)
    centro_territorial_pk = request.session.get('centro_territorial_pk')
    if centro_territorial_pk:
        centro = Centro.objects.filter(pk=centro_territorial_pk).first()
        if centro and centro.centro_padre_id:
            return Departamento.objects.filter(centro_id=centro.centro_padre_id)
        return Departamento.objects.filter(centro_id=centro_territorial_pk)
    if depto and not depto.restringido:
        return Departamento.objects.all()
    return Departamento.objects.none()


def _ids_alcanzables(request):
    return set(alcanzar_departamentos(request).values_list('pk', flat=True))


def _municipios_centro(request):
    """Municipios que atiende el centro territorial de la sesión (o None si no
    hay sesión territorial: entonces se ven todos los municipios)."""
    centro_pk = request.session.get('centro_territorial_pk')
    if not centro_pk:
        return None
    centro = Centro.objects.filter(pk=centro_pk).first()
    return centro.municipios_atendidos.all() if centro else Municipio.objects.none()


def _equipos_visibles(request):
    """Equipos visibles para la sesión: alcance por departamentos y, si hay
    sesión territorial, SOLO los de los municipios que atiende."""
    qs = Equipo.objects.filter(departamento_id__in=_ids_alcanzables(request)).select_related('departamento', 'municipio')
    municipios = _municipios_centro(request)
    if municipios is not None:
        qs = qs.filter(municipio_id__in=municipios)
    return qs


def _personas_visibles(request):
    """Personas visibles para la sesión: las de sus departamentos y SOLO del
    centro donde la sesión vive. El territorial NO ve las personas del centro
    padre (y el provincial no ve las del territorial): cada persona pertenece
    al centro donde se creó (centro_origen). Staff/visitante ven todas."""
    if request.user.is_staff or request.session.get('is_visitor'):
        return Persona.objects.all()
    qs = Persona.objects.filter(departamento_id__in=_ids_propios(request))
    centro_pk = request.session.get('centro_territorial_pk')
    if centro_pk:
        return qs.filter(centro_origen_id=centro_pk)
    return qs.filter(centro_origen__isnull=True)


def _ids_propios(request):
    """Alcance de PERSONAS y ÓRDENES: cada departamento ve SOLO el suyo
    (aunque sea global); staff y visitante ven todo."""
    if request.user.is_staff or request.session.get('is_visitor'):
        return set(Departamento.objects.all().values_list('pk', flat=True))
    depto = _departamento_sesion(request)
    if depto:
        return {depto.pk}
    return set()


def _denegar(request, url_name):
    messages.error(request, 'No tienes permiso para acceder a este registro.')
    return redirect(url_name)


def _mes_actual_range():
    hoy = timezone.now().date()
    inicio_mes = date(hoy.year, hoy.month, 1)
    ultimo_dia = calendar.monthrange(hoy.year, hoy.month)[1]
    fin_mes = date(hoy.year, hoy.month, ultimo_dia)
    return inicio_mes, fin_mes


def _get_periodo_activo(request):
    pk = request.session.get('periodo_pk')
    if pk:
        try:
            return Periodo.objects.get(pk=pk)
        except Periodo.DoesNotExist:
            pass
    return Periodo.objects.first()


def _persona_sesion(request):
    persona_id = request.session.get('persona_id')
    if not persona_id:
        return None
    return Persona.objects.filter(pk=persona_id).first()


def _mismo_centro(request, equipo):
    """P2-D7: la sesión territorial opera SOLO los equipos de los municipios que
    atiende (los equipos del centro padre en esos municipios, con aprobación del
    dueño); el resto (provincial, staff, visitante) opera en cualquier centro."""
    centro_pk = request.session.get('centro_territorial_pk')
    if not centro_pk:
        return True
    if equipo.municipio_id is None:
        return False
    centro = Centro.objects.filter(pk=centro_pk).first()
    if centro is None:
        return False
    return centro.municipios_atendidos.filter(pk=equipo.municipio_id).exists()


def _snapshot_equipo(equipo):
    """Snapshot JSON con los valores PREVIOS de los 17 campos editables (D1)."""
    snap = {}
    for campo in CAMPO_SNAPSHOT:
        valor = getattr(equipo, campo)
        snap[campo] = valor.pk if hasattr(valor, 'pk') else valor
    return snap


def _restaurar_snapshot(equipo, snapshot):
    """Restaura los campos editables de un Equipo desde un snapshot (D1)."""
    for campo in CAMPO_SNAPSHOT:
        if campo not in snapshot:
            continue
        valor = snapshot[campo]
        if campo == 'municipio':
            equipo.municipio_id = valor
        elif campo == 'departamento':
            equipo.departamento_id = valor
        else:
            setattr(equipo, campo, valor)
    equipo.save(update_fields=CAMPO_SNAPSHOT)


def _ordenes_habilitadas(request):
    """Gating D6 + servicio por departamento: solo staff/visitante y los
    departamentos con servicio_ordenes activo usan el módulo de órdenes.
    Los centros territoriales NO usan el módulo: es exclusivo del
    departamento Imagenología del centro provincial (centro padre)."""
    if not get_configuracion().mostrar_ordenes_servicio:
        messages.error(request, 'El módulo de órdenes de servicio está desactivado.')
        return False
    if request.user.is_staff or request.session.get('is_visitor'):
        return True
    if request.session.get('centro_territorial_pk'):
        messages.error(request, 'El módulo de órdenes de servicio solo está disponible en el centro provincial.')
        return False
    depto = _departamento_sesion(request)
    if depto and depto.servicio_ordenes:
        return True
    messages.error(request, 'El módulo de órdenes de servicio no está habilitado para este departamento.')
    return False


def login_view(request):
    if request.user.is_authenticated:
        return redirect('select_persona')
    config = get_configuracion()

    # Paso 1: si la etiqueta del centro está activa (vieja o nueva, C5) y aún no se
    # entró como centro, se exige el login del centro ANTES del login de departamento.
    if (config.exigir_login_centro or config.permitir_login_centros_territoriales) and not request.session.get('centro_ok'):
        if request.method == 'POST':
            modo = request.POST.get('modo_login', 'centro')
            form_centro = LoginCentroForm(request.POST)
            if form_centro.is_valid():
                superadmin = form_centro.cleaned_data.get('superadmin')
                if superadmin is not None:
                    auth_login(request, superadmin)
                    messages.success(request, 'Bienvenido, Super Admin (acceso global).')
                    return redirect('select_persona')
                centro = form_centro.cleaned_data.get('centro') or centro_provincial_por_defecto()
                request.session['centro_pk'] = centro.pk
                if centro.tipo == 'territorial':
                    request.session['centro_territorial_pk'] = centro.pk
                request.session['centro_ok'] = True
                messages.success(request, 'Bienvenido al centro. Ahora elige tu departamento.')
                return redirect('login')
            return render(request, 'inventario/login.html', {
                'form_centro': form_centro,
                'modo_centro': True,
                'config': config,
            })
        return render(request, 'inventario/login.html', {
            'form_centro': LoginCentroForm(),
            'modo_centro': True,
            'config': config,
        })

    # Paso 2: login de departamento (o super admin con la contraseña maestra).
    if request.method == 'POST':
        modo = request.POST.get('modo_login', 'departamento')
        if modo == 'departamento':
            form_departamento = LoginDepartamentoForm(request.POST, centro_pk=request.session.get('centro_pk'))
            if form_departamento.is_valid():
                superadmin = form_departamento.cleaned_data.get('superadmin')
                if superadmin is not None:
                    # Entró con la contraseña maestra: super admin GLOBAL.
                    # El departamento elegido solo es el punto de entrada.
                    auth_login(request, superadmin)
                    request.session.pop('departamento_pk', None)
                    messages.success(request, 'Bienvenido, Super Admin (acceso global).')
                    return redirect('select_persona')
                depto = form_departamento.cleaned_data['departamento']
                request.session['departamento_pk'] = depto.pk
                messages.success(request, f'Sesión iniciada en el departamento {depto.nombre}.')
                return redirect('select_persona')
            form_admin = LoginForm()
            return render(request, 'inventario/login.html', {
                'form_departamento': form_departamento,
                'form_admin': form_admin,
                'tab_activa': 'departamento',
                'config': config,
            })
        form_admin = LoginForm(request, data=request.POST)
        if form_admin.is_valid():
            user = form_admin.get_user()
            if not user.is_staff:
                form_admin.add_error(None, 'Esta cuenta no tiene permisos administrativos.')
            else:
                auth_login(request, user)
                messages.success(request, f'Bienvenido, {user.username}.')
                return redirect('select_persona')
        form_departamento = LoginDepartamentoForm()
        return render(request, 'inventario/login.html', {
            'form_departamento': form_departamento,
            'form_admin': form_admin,
            'tab_activa': 'admin',
            'config': config,
        })
    form_departamento = LoginDepartamentoForm(centro_pk=request.session.get('centro_pk'))
    form_admin = LoginForm()
    return render(request, 'inventario/login.html', {
        'form_departamento': form_departamento,
        'form_admin': form_admin,
        'tab_activa': 'departamento',
        'config': config,
    })


def logout_view(request):
    auth_logout(request)
    for key in ['persona_id', 'persona_nombre', 'is_visitor', 'visitor_link_id', 'departamento_pk', 'centro_ok', 'centro_pk', 'centro_territorial_pk']:
        request.session.pop(key, None)
    messages.info(request, 'Sesión cerrada correctamente.')
    return redirect('login')


def crear_departamento(request):
    es_staff = request.user.is_authenticated and request.user.is_staff
    if request.user.is_authenticated and not es_staff:
        return redirect('select_persona')
    # Los centros territoriales NO crean departamentos: heredan los del padre.
    if request.session.get('centro_territorial_pk'):
        messages.error(request, 'Los centros territoriales no crean departamentos: usan los del centro padre.')
        return redirect('login')
    # Solo quien pasó por el login del centro (o entró como super admin) puede crear departamentos.
    if not es_staff and not request.session.get('centro_ok') and not request.user.is_superuser:
        messages.error(request, 'Debes pasar por el login del centro para poder crear un departamento.')
        return redirect('login')
    if request.method == 'POST':
        form = CrearDepartamentoForm(request.POST)
        if form.is_valid():
            depto = Departamento.objects.create(
                nombre=form.cleaned_data['nombre'],
                contrasena=make_password(form.cleaned_data['contrasena']),
                restringido=True,
                activo=True,
            )
            if es_staff:
                messages.success(request, f'Departamento "{depto.nombre}" creado.')
                return redirect('departamentos_admin')
            request.session['departamento_pk'] = depto.pk
            messages.success(request, f'Departamento "{depto.nombre}" creado. Ahora selecciona a la persona.')
            return redirect('select_persona')
    else:
        form = CrearDepartamentoForm()
    return render(request, 'inventario/crear_departamento.html', {'form': form})


def departamentos_admin(request):
    if not request.user.is_staff:
        return redirect('login')
    counts_personas = Persona.objects.values('departamento_id').annotate(n=Count('id'))
    counts_equipos = Equipo.objects.values('departamento_id').annotate(n=Count('id'))
    counts_p = {d['departamento_id']: d['n'] for d in counts_personas}
    counts_e = {d['departamento_id']: d['n'] for d in counts_equipos}
    departamentos = Departamento.objects.annotate(n_links=Count('personas')).all()
    return render(request, 'inventario/departamentos_admin.html', {
        'departamentos': departamentos,
        'counts_personas': counts_p,
        'counts_equipos': counts_e,
        'form_contrasena_centro': ConfiguracionContrasenaForm(),
    })


def configuracion_toggle_etiqueta(request, etiqueta):
    if not request.user.is_staff:
        return redirect('login')
    config = get_configuracion()
    if etiqueta == 'exigir_login_centro':
        config.exigir_login_centro = not config.exigir_login_centro
        config.save(update_fields=['exigir_login_centro'])
        estado = 'activado' if config.exigir_login_centro else 'desactivado'
        messages.success(request, f'Etiqueta "exigir login del centro" {estado}.')
    elif etiqueta == 'exigir_contrasena_personas':
        config.exigir_contrasena_personas = not config.exigir_contrasena_personas
        config.save(update_fields=['exigir_contrasena_personas'])
        estado = 'activado' if config.exigir_contrasena_personas else 'desactivado'
        messages.success(request, f'Etiqueta "exigir contraseña de personas" {estado}.')
    elif etiqueta == 'permitir_login_centros_territoriales':
        config.permitir_login_centros_territoriales = not config.permitir_login_centros_territoriales
        config.save(update_fields=['permitir_login_centros_territoriales'])
        estado = 'activado' if config.permitir_login_centros_territoriales else 'desactivado'
        messages.success(request, f'Etiqueta "permitir login de centros territoriales" {estado}.')
    elif etiqueta == 'mostrar_aprobaciones':
        config.mostrar_aprobaciones = not config.mostrar_aprobaciones
        config.save(update_fields=['mostrar_aprobaciones'])
        estado = 'activado' if config.mostrar_aprobaciones else 'desactivado'
        messages.success(request, f'Etiqueta "mostrar aprobaciones" {estado}.')
    elif etiqueta == 'mostrar_ordenes_servicio':
        config.mostrar_ordenes_servicio = not config.mostrar_ordenes_servicio
        config.save(update_fields=['mostrar_ordenes_servicio'])
        estado = 'activado' if config.mostrar_ordenes_servicio else 'desactivado'
        messages.success(request, f'Etiqueta "mostrar órdenes de servicio" {estado}.')
    else:
        messages.error(request, 'Etiqueta desconocida.')
    return redirect('departamentos_admin')


def configuracion_cambiar_contrasena_centro(request):
    if not request.user.is_staff:
        return redirect('login')
    if request.method == 'POST':
        form = ConfiguracionContrasenaForm(request.POST)
        if form.is_valid():
            config = get_configuracion()
            config.contrasena_centro = make_password(form.cleaned_data['contrasena'])
            config.save(update_fields=['contrasena_centro'])
            messages.success(request, 'Contraseña del centro actualizada.')
    return redirect('departamentos_admin')


def departamento_toggle_restringido(request, pk):
    if not request.user.is_staff:
        return redirect('login')
    departamento = get_object_or_404(Departamento, pk=pk)
    if request.method == 'POST':
        departamento.restringido = not departamento.restringido
        departamento.save(update_fields=['restringido'])
        etiqueta = 'restricción' if departamento.restringido else 'acceso global'
        messages.success(request, f'Departamento "{departamento.nombre}" ahora tiene {etiqueta}.')
    return redirect('departamentos_admin')


def departamento_toggle_activo(request, pk):
    if not request.user.is_staff:
        return redirect('login')
    departamento = get_object_or_404(Departamento, pk=pk)
    if request.method == 'POST':
        departamento.activo = not departamento.activo
        departamento.save(update_fields=['activo'])
        estado = 'activado' if departamento.activo else 'desactivado'
        messages.success(request, f'Departamento "{departamento.nombre}" {estado}.')
    return redirect('departamentos_admin')


def departamento_editar(request, pk):
    if not request.user.is_staff:
        return redirect('login')
    departamento = get_object_or_404(Departamento, pk=pk)
    if request.method == 'POST':
        form = DepartamentoEditarForm(request.POST, instance=departamento)
        if form.is_valid():
            form.save()
            messages.success(request, f'Departamento actualizado a "{form.cleaned_data["nombre"]}".')
            return redirect('departamentos_admin')
    else:
        form = DepartamentoEditarForm(instance=departamento)
    return render(request, 'inventario/departamento_form.html', {
        'form': form, 'departamento': departamento, 'accion': 'Editar nombre',
    })


def departamento_contrasena(request, pk):
    """Cambia la contraseña del departamento. Si la sesión es de un centro
    territorial, la contraseña se guarda como LOCAL de ese centro (el
    departamento del padre no se altera); si no, se cambia la del propio
    departamento. Puede usarla el staff (cualquier departamento) o el propio
    departamento en sesión."""
    departamento = get_object_or_404(Departamento, pk=pk)
    es_staff = request.user.is_authenticated and request.user.is_staff
    depto_sesion = _departamento_sesion(request)
    propio = depto_sesion is not None and depto_sesion.pk == departamento.pk
    if not es_staff and not propio:
        return _denegar(request, 'dashboard')
    centro_territorial_pk = request.session.get('centro_territorial_pk')
    centro = Centro.objects.filter(pk=centro_territorial_pk).first() if centro_territorial_pk else None
    if request.method == 'POST':
        form = DepartamentoContrasenaForm(request.POST)
        if form.is_valid():
            nueva = make_password(form.cleaned_data['contrasena'])
            if centro is not None and centro.tipo == 'territorial':
                DepartamentoCentro.objects.update_or_create(
                    departamento=departamento, centro=centro,
                    defaults={'contrasena': nueva},
                )
                _auditar(request, 'editar', 'Centro', centro.pk,
                         f'Contraseña local de {departamento.nombre} en {centro.nombre}')
                messages.success(request, f'Contraseña local de "{departamento.nombre}" en {centro.nombre} actualizada.')
            else:
                departamento.contrasena = nueva
                departamento.save(update_fields=['contrasena'])
                _auditar(request, 'editar', 'Departamento', departamento.pk,
                         f'Contraseña de {departamento.nombre} actualizada')
                messages.success(request, f'Contraseña de "{departamento.nombre}" actualizada.')
            if es_staff:
                return redirect('departamentos_admin')
            return redirect('dashboard')
    else:
        form = DepartamentoContrasenaForm()
    return render(request, 'inventario/departamento_form.html', {
        'form': form, 'departamento': departamento, 'accion': 'Cambiar contraseña',
    })


def select_persona(request):
    if not _tiene_sesion(request):
        return redirect('login')
    config = get_configuracion()
    if request.user.is_superuser:
        return redirect('admin_panel')
    ids = _ids_propios(request)
    if request.method == 'POST':
        if 'persona_id' in request.POST:
            persona_id = request.POST.get('persona_id')
            try:
                persona = _personas_visibles(request).get(pk=persona_id, activo=True)
            except Persona.DoesNotExist:
                messages.error(request, 'Persona no encontrada.')
                return redirect('select_persona')
            if persona.departamento_id not in ids:
                messages.error(request, 'No tienes permiso para iniciar sesión como esa persona.')
                return redirect('select_persona')
            # Si la etiqueta de contraseñas de personas está activa, se exige la contraseña.
            if config.exigir_contrasena_personas:
                contrasena = request.POST.get('contrasena_persona', '')
                if not persona.contrasena:
                    messages.error(request, f'La persona {persona} aún no tiene contraseña asignada. Pide al Super Admin que la configure.')
                    return redirect('select_persona')
                if not check_password(contrasena, persona.contrasena):
                    messages.error(request, 'Contraseña incorrecta para esa persona.')
                    return redirect('select_persona')
            request.session['persona_id'] = persona.pk
            request.session['persona_nombre'] = str(persona)
            messages.success(request, f'Has iniciado sesión como {persona}.')
            return redirect('dashboard')
        elif 'nombre' in request.POST:
            form = QuickPersonaForm(request.POST)
            if form.is_valid():
                persona = form.save(commit=False)
                persona.apellido = persona.nombre
                persona.activo = True
                departamento = _departamento_sesion(request) or Departamento.objects.first()
                if departamento is None:
                    departamento, _ = Departamento.objects.get_or_create(nombre='Imagenología')
                persona.departamento = departamento
                centro_pk = request.session.get('centro_territorial_pk')
                persona.centro_origen = Centro.objects.filter(pk=centro_pk).first() if centro_pk else None
                persona.save()
                messages.success(request, f'Persona "{persona.nombre}" creada. Selecciónala para iniciar.')
                return redirect('select_persona')
            else:
                personas = _personas_visibles(request).filter(activo=True).order_by('apellido', 'nombre')
                return render(request, 'inventario/select_persona.html', {
                    'personas': personas,
                    'form': form,
                    'config': config,
                })
        return redirect('select_persona')
    personas = _personas_visibles(request).filter(activo=True).order_by('apellido', 'nombre')
    form = QuickPersonaForm()
    mostrar_departamento = len(ids) > 1 or request.user.is_superuser
    return render(request, 'inventario/select_persona.html', {
        'personas': personas,
        'form': form,
        'mostrar_departamento': mostrar_departamento,
        'config': config,
    })


def dashboard(request):
    if not _tiene_sesion(request):
        return redirect('login')
    persona_id = request.session.get('persona_id')
    ids = _ids_propios(request)

    pk = request.GET.get('periodo')
    if pk:
        try:
            periodo = Periodo.objects.get(pk=pk)
            request.session['periodo_pk'] = periodo.pk
        except (Periodo.DoesNotExist, ValueError):
            periodo = _get_periodo_activo(request)
    else:
        periodo = _get_periodo_activo(request)

    if periodo:
        inicio, fin = periodo.fecha_inicio, periodo.fecha_fin
    else:
        inicio, fin = _mes_actual_range()

    personas = _personas_visibles(request).filter(activo=True).annotate(
        total_act=Sum('asignaciones__acciones', filter=Q(
            asignaciones__fecha__gte=inicio, asignaciones__fecha__lte=fin,
        )),
        total_hd=Sum('asignaciones__horas_diurnas', filter=Q(
            asignaciones__fecha__gte=inicio, asignaciones__fecha__lte=fin,
        )),
        total_he=Sum('asignaciones__horas_extras', filter=Q(
            asignaciones__fecha__gte=inicio, asignaciones__fecha__lte=fin,
        )),
        total_ordenes_legacy=Count('asignaciones__orden_trabajo', distinct=True, filter=Q(
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
        total_ordenes_partes=Count('partes__parte', distinct=True, filter=Q(
            partes__parte__fecha_inicio__gte=inicio,
            partes__parte__fecha_fin__lte=fin,
        )),
    ).order_by('apellido', 'nombre')

    for p in personas:
        p.total_act = (p.total_act or 0) + (p.partes_act or 0)
        p.total_hd = (p.total_hd or 0) + (p.partes_hd or 0)
        p.total_he = (p.total_he or 0) + (p.partes_he or 0)
        p.total_horas = p.total_hd + p.total_he
        p.total_ordenes = (p.total_ordenes_legacy or 0) + (p.total_ordenes_partes or 0)

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
        'inicio': inicio,
        'fin': fin,
        'total_acciones_global': total_acciones_global,
        'total_horas_global': total_horas_global,
        'total_he_global': total_he_global,
        # P4: el panel completo (nombre, órdenes, acciones, horas) SOLO lo ve el
        # departamento Imagenología del centro PROVINCIAL (y staff/visitante).
        # Los centros territoriales y demás departamentos ven SOLO los nombres
        # de sus integrantes.
        'modo_integrantes': bool(
            _departamento_sesion(request)
            and not request.user.is_staff
            and not request.session.get('is_visitor')
            and (
                not _departamento_sesion(request).servicio_ordenes
                or request.session.get('centro_territorial_pk')
            )
        ),
    }
    return render(request, 'inventario/dashboard.html', context)


def persona_list(request):
    if not _tiene_sesion(request):
        return redirect('login')
    # P4: la vista de personas es exclusiva del Super Admin (y del modo visita
    # de solo lectura); los departamentos registran personas al loguearse.
    if not (request.user.is_staff or request.session.get('is_visitor')):
        messages.error(request, 'La gestión de personas se realiza al iniciar sesión en el departamento. Esta vista es exclusiva del Super Admin.')
        return redirect('dashboard')
    ids = _ids_propios(request)
    query = request.GET.get('q', '')
    periodo = _get_periodo_activo(request)
    if periodo:
        fi, ff = periodo.fecha_inicio, periodo.fecha_fin
    else:
        fi, ff = _mes_actual_range()

    personas = _personas_visibles(request)
    if query:
        personas = personas.filter(
            Q(nombre__icontains=query) | Q(apellido__icontains=query) |
            Q(email__icontains=query) | Q(telefono__icontains=query)
        )
    personas = personas.annotate(
        total_act=Sum('asignaciones__acciones', filter=Q(asignaciones__fecha__gte=fi, asignaciones__fecha__lte=ff)),
        total_hd=Sum('asignaciones__horas_diurnas', filter=Q(asignaciones__fecha__gte=fi, asignaciones__fecha__lte=ff)),
        total_he=Sum('asignaciones__horas_extras', filter=Q(asignaciones__fecha__gte=fi, asignaciones__fecha__lte=ff)),
        partes_act=Sum('partes__parte__total_acciones', filter=Q(
            partes__parte__fecha_inicio__gte=fi, partes__parte__fecha_fin__lte=ff,
        )),
        partes_hd=Sum('partes__horas_trabajadas', filter=Q(
            partes__parte__fecha_inicio__gte=fi, partes__parte__fecha_fin__lte=ff,
        )),
        partes_he=Sum('partes__horas_extras', filter=Q(
            partes__parte__fecha_inicio__gte=fi, partes__parte__fecha_fin__lte=ff,
        )),
    ).order_by('apellido', 'nombre')

    for p in personas:
        p.total_act = (p.total_act or 0) + (p.partes_act or 0)
        p.total_hd = (p.total_hd or 0) + (p.partes_hd or 0)
        p.total_he = (p.total_he or 0) + (p.partes_he or 0)

    paginator = Paginator(personas, 20)
    page = request.GET.get('page', 1)
    personas_page = paginator.get_page(page)

    return render(request, 'inventario/persona_list.html', {
        'personas': personas_page,
        'query': query,
        'mostrar_departamento': len(ids) > 1 or request.user.is_superuser,
    })


def persona_create(request):
    if not _tiene_sesion(request):
        return redirect('login')
    if not request.user.is_staff:
        messages.error(request, 'La gestión de personas es exclusiva del Super Admin.')
        return redirect('dashboard')
    depto = _departamento_sesion(request)
    departamentos = alcanzar_departamentos(request)
    if request.method == 'POST':
        form = PersonaForm(request.POST, departamento=depto, departamentos=departamentos)
        if form.is_valid():
            persona = form.save(commit=False)
            centro_pk = request.session.get('centro_territorial_pk')
            persona.centro_origen = Centro.objects.filter(pk=centro_pk).first() if centro_pk else None
            persona.save()
            messages.success(request, 'Persona registrada correctamente.')
            return redirect('persona_list')
    else:
        form = PersonaForm(departamento=depto, departamentos=departamentos)
    return render(request, 'inventario/persona_form.html', {'form': form, 'accion': 'Registrar'})


def persona_update(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    if not request.user.is_staff:
        messages.error(request, 'La gestión de personas es exclusiva del Super Admin.')
        return redirect('dashboard')
    persona = get_object_or_404(Persona, pk=pk)
    if not _personas_visibles(request).filter(pk=persona.pk).exists():
        return _denegar(request, 'persona_list')
    depto = _departamento_sesion(request)
    departamentos = alcanzar_departamentos(request)
    desc = str(persona)
    if request.method == 'POST':
        form = PersonaForm(request.POST, instance=persona, departamento=depto, departamentos=departamentos)
        if form.is_valid():
            persona = form.save(commit=False)
            centro_pk = request.session.get('centro_territorial_pk')
            persona.centro_origen = Centro.objects.filter(pk=centro_pk).first() if centro_pk else None
            persona.save()
            _auditar(request, 'editar', 'Persona', persona.pk, desc)
            messages.success(request, 'Persona actualizada correctamente.')
            return redirect('persona_list')
    else:
        form = PersonaForm(instance=persona, departamento=depto, departamentos=departamentos)
    return render(request, 'inventario/persona_form.html', {
        'form': form, 'accion': 'Editar', 'persona': persona
    })


def persona_delete(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    if not request.user.is_staff:
        messages.error(request, 'La gestión de personas es exclusiva del Super Admin.')
        return redirect('dashboard')
    persona = get_object_or_404(Persona, pk=pk)
    if not _personas_visibles(request).filter(pk=persona.pk).exists():
        return _denegar(request, 'persona_list')
    desc = str(persona)
    if request.method == 'POST':
        _auditar(request, 'eliminar', 'Persona', persona.pk, desc)
        persona.delete()
        messages.success(request, f'Persona "{desc}" eliminada correctamente.')
        return redirect('persona_list')
    return render(request, 'inventario/persona_confirm_delete.html', {'persona': persona})


def persona_detail(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    # P4: solo el Super Admin (o modo visita) accede al detalle de personas.
    if not (request.user.is_staff or request.session.get('is_visitor')):
        messages.error(request, 'La gestión de personas se realiza al iniciar sesión en el departamento. Esta vista es exclusiva del Super Admin.')
        return redirect('dashboard')
    persona = get_object_or_404(Persona, pk=pk)
    if not _personas_visibles(request).filter(pk=persona.pk).exists():
        return _denegar(request, 'persona_list')
    periodo = _get_periodo_activo(request)

    if periodo:
        fi, ff = periodo.fecha_inicio, periodo.fecha_fin
    else:
        fi, ff = _mes_actual_range()

    asignaciones = Asignacion.objects.filter(
        persona=persona, fecha__gte=fi, fecha__lte=ff
    ).select_related('orden_trabajo').order_by('fecha')

    partes = PartePersona.objects.filter(
        persona=persona,
        parte__fecha_inicio__gte=fi,
        parte__fecha_fin__lte=ff,
    ).select_related('parte').order_by('parte__fecha_inicio')

    total_act = sum(a.acciones for a in asignaciones) + sum(pp.parte.total_acciones for pp in partes)
    total_hd = sum(a.horas_diurnas for a in asignaciones) + sum(pp.horas_trabajadas for pp in partes)
    total_he = sum(a.horas_extras for a in asignaciones) + sum(pp.horas_extras for pp in partes)

    return render(request, 'inventario/persona_detail.html', {
        'persona': persona,
        'asignaciones': asignaciones,
        'partes': partes,
        'total_act': total_act,
        'total_hd': total_hd,
        'total_he': total_he,
        'inicio': fi,
        'fin': ff,
    })


def orden_list(request):
    if not _tiene_sesion(request):
        return redirect('login')
    if not _ordenes_habilitadas(request):
        return redirect('dashboard')
    ids = _ids_propios(request)
    query = request.GET.get('q', '')
    estado = request.GET.get('estado', '')
    f_persona = request.GET.get('persona', '')

    from itertools import chain

    ordenes_qs = OrdenTrabajo.objects.filter(departamento_id__in=ids).prefetch_related('asignaciones__persona').annotate(
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

    partes_qs = ParteTrabajo.objects.filter(departamento_id__in=ids).prefetch_related('personas__persona', 'creado_por')
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

    periodo = _get_periodo_activo(request)
    if periodo:
        p_inicio, p_fin = periodo.fecha_inicio, periodo.fecha_fin
    else:
        p_inicio = p_fin = None

    def sort_key(item):
        f = item['fecha']
        if p_inicio and p_fin and p_inicio <= f <= p_fin:
            return (0, -f.toordinal())
        return (1, -f.toordinal())

    items = sorted(
        chain(
            (orden_to_item(o) for o in ordenes_qs),
            (parte_to_item(p) for p in partes_qs),
        ),
        key=sort_key,
    )

    paginator = Paginator(items, 20)
    page = request.GET.get('page', 1)
    items_page = paginator.get_page(page)

    personas = Persona.objects.filter(activo=True, departamento_id__in=ids).order_by('apellido', 'nombre')

    return render(request, 'inventario/orden_list.html', {
        'items': items_page,
        'query': query,
        'estado': estado,
        'f_persona': f_persona,
        'personas': personas,
    })


def orden_create(request):
    if not _tiene_sesion(request):
        return redirect('login')
    if not _ordenes_habilitadas(request):
        return redirect('dashboard')
    depto = _departamento_sesion(request)
    departamentos = alcanzar_departamentos(request)
    if request.method == 'POST':
        form = OrdenTrabajoForm(request.POST, departamento=depto, departamentos=departamentos)
        if form.is_valid():
            orden = form.save()
            messages.success(request, f'Orden de Trabajo OT-{orden.numero_orden} creada correctamente.')
            return redirect('orden_detail', pk=orden.pk)
    else:
        form = OrdenTrabajoForm(departamento=depto, departamentos=departamentos)
    return render(request, 'inventario/orden_form.html', {'form': form, 'accion': 'Crear'})


def orden_update(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    if not _ordenes_habilitadas(request):
        return redirect('dashboard')
    orden = get_object_or_404(OrdenTrabajo, pk=pk)
    if orden.departamento_id not in _ids_alcanzables(request):
        return _denegar(request, 'orden_list')
    depto = _departamento_sesion(request)
    departamentos = alcanzar_departamentos(request)
    desc = str(orden)
    if request.method == 'POST':
        form = OrdenTrabajoForm(request.POST, instance=orden, departamento=depto, departamentos=departamentos)
        if form.is_valid():
            form.save()
            _auditar(request, 'editar', 'Orden de Trabajo', orden.pk, desc)
            messages.success(request, 'Orden de Trabajo actualizada correctamente.')
            return redirect('orden_detail', pk=orden.pk)
    else:
        form = OrdenTrabajoForm(instance=orden, departamento=depto, departamentos=departamentos)
    return render(request, 'inventario/orden_form.html', {
        'form': form, 'accion': 'Editar', 'orden': orden
    })


def orden_detail(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    if not _ordenes_habilitadas(request):
        return redirect('dashboard')
    orden = get_object_or_404(
        OrdenTrabajo.objects.prefetch_related(
            'asignaciones__persona'
        ), pk=pk
    )
    if orden.departamento_id not in _ids_alcanzables(request):
        return _denegar(request, 'orden_list')
    personas_activas = Persona.objects.filter(
        activo=True, departamento_id__in=_ids_alcanzables(request)
    ).order_by('apellido', 'nombre')
    asignaciones = orden.asignaciones.select_related('persona').all()

    if request.method == 'POST':
        form = AsignacionForm(request.POST, personas_qs=personas_activas)
        if form.is_valid():
            asignacion = form.save(commit=False)
            asignacion.orden_trabajo = orden
            asignacion.save()
            messages.success(request, f'{asignacion.persona} agregado a la orden correctamente.')
            return redirect('orden_detail', pk=orden.pk)
    else:
        form = AsignacionForm(personas_qs=personas_activas)

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
    if not _tiene_sesion(request):
        return redirect('login')
    if not _ordenes_habilitadas(request):
        return redirect('dashboard')
    orden = get_object_or_404(OrdenTrabajo, pk=pk)
    if orden.departamento_id not in _ids_alcanzables(request):
        return _denegar(request, 'orden_list')
    desc = str(orden)
    if request.method == 'POST':
        _auditar(request, 'eliminar', 'Orden de Trabajo', orden.pk, desc)
        orden.delete()
        messages.success(request, f'{desc} eliminada correctamente.')
        return redirect('orden_list')
    return render(request, 'inventario/orden_confirm_delete.html', {'orden': orden})


def asignacion_delete(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    asignacion = get_object_or_404(Asignacion, pk=pk)
    if asignacion.orden_trabajo.departamento_id not in _ids_alcanzables(request):
        return _denegar(request, 'orden_list')
    orden_pk = asignacion.orden_trabajo.pk
    if request.method == 'POST':
        asignacion.delete()
        messages.success(request, 'Asignación eliminada correctamente.')
        return redirect('orden_detail', pk=orden_pk)
    return render(request, 'inventario/asignacion_confirm_delete.html', {'asignacion': asignacion})


def generar_orden(request):
    if not _tiene_sesion(request):
        return redirect('login')
    if not _ordenes_habilitadas(request):
        return redirect('dashboard')
    persona_id = request.session.get('persona_id')
    try:
        persona_actual = Persona.objects.get(pk=persona_id) if persona_id else None
    except Persona.DoesNotExist:
        persona_actual = None

    depto = _departamento_sesion(request)
    departamentos = alcanzar_departamentos(request)
    personas_qs = Persona.objects.filter(
        activo=True, departamento_id__in=_ids_alcanzables(request)
    ).order_by('apellido', 'nombre')

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
        form = ParteTrabajoForm(
            request.POST, departamento=depto, departamentos=departamentos,
            personas_qs=personas_qs,
            persona_inicial=persona_actual, fecha_min=fecha_min, fecha_max=fecha_max,
        )
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
                personas_qs = Persona.objects.filter(activo=True, departamento_id__in=_ids_alcanzables(request))
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
        form = ParteTrabajoForm(
            departamento=depto, departamentos=departamentos, personas_qs=personas_qs,
            persona_inicial=persona_actual, fecha_min=fecha_min, fecha_max=fecha_max,
        )

    return render(request, 'inventario/generar_orden.html', {
        'form': form,
        'persona_actual': persona_actual,
        'personas_iniciales': personas_iniciales,
        'fecha_min': fecha_min,
        'fecha_max': fecha_max,
    })


def parte_update(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    parte = get_object_or_404(ParteTrabajo, pk=pk)
    if parte.departamento_id not in _ids_alcanzables(request):
        return _denegar(request, 'orden_list')
    depto = _departamento_sesion(request)
    departamentos = alcanzar_departamentos(request)
    personas_qs = Persona.objects.filter(
        activo=True, departamento_id__in=_ids_alcanzables(request)
    ).order_by('apellido', 'nombre')
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

    if request.method == 'POST':
        form = ParteTrabajoForm(
            request.POST, instance=parte, departamento=depto, departamentos=departamentos,
            personas_qs=personas_qs,
            persona_inicial=persona_actual, fecha_min=fecha_min, fecha_max=fecha_max,
        )
        if form.is_valid():
            parte = form.save()
            PartePersona.objects.filter(parte=parte).delete()
            for p in form.cleaned_data['personas']:
                PartePersona.objects.create(
                    parte=parte, persona=p,
                    horas_trabajadas=form.cleaned_data['horas_trabajadas'],
                    horas_extras=form.cleaned_data['horas_extras'],
                )
            messages.success(request, f'Parte #{parte.pk} actualizado correctamente.')
            return redirect('orden_list')
    else:
        initial_hd = None
        initial_he = None
        pp = PartePersona.objects.filter(parte=parte).first()
        if pp:
            initial_hd = pp.horas_trabajadas
            initial_he = pp.horas_extras
        form = ParteTrabajoForm(
            instance=parte, departamento=depto, departamentos=departamentos,
            personas_qs=personas_qs,
            persona_inicial=persona_actual,
            initial={
                'personas': PartePersona.objects.filter(parte=parte).values_list('persona_id', flat=True),
                'horas_trabajadas': initial_hd,
                'horas_extras': initial_he,
            },
        )

    return render(request, 'inventario/parte_form.html', {
        'form': form, 'parte': parte, 'accion': 'Editar',
    })


def parte_delete(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    parte = get_object_or_404(ParteTrabajo, pk=pk)
    if parte.departamento_id not in _ids_alcanzables(request):
        return _denegar(request, 'orden_list')
    if request.method == 'POST':
        parte.delete()
        messages.success(request, 'Parte de trabajo eliminado correctamente.')
        return redirect('orden_list')
    return render(request, 'inventario/parte_confirm_delete.html', {'parte': parte})


def equipo_list(request):
    if not _tiene_sesion(request):
        return redirect('login')
    ids = _ids_alcanzables(request)
    q = request.GET.get('q', '')
    f_marca = request.GET.get('marca', '')
    f_modelo = request.GET.get('modelo', '')
    f_unidad = request.GET.getlist('unidad')
    f_municipio = request.GET.get('municipio', '')
    f_estado = request.GET.get('estado', '')

    equipos = _equipos_visibles(request)
    if q:
        equipos = equipos.filter(
            Q(marca__icontains=q) | Q(municipio__nombre__icontains=q) |
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
        equipos = equipos.filter(municipio__nombre=f_municipio)
    if f_estado:
        equipos = equipos.filter(estado=f_estado)

    scoped = _equipos_visibles(request)
    marcas = scoped.values_list('marca', flat=True).exclude(marca='').distinct().order_by('marca')
    modelos = scoped.values_list('modelo', flat=True).exclude(modelo='').distinct().order_by('modelo')
    unidades = scoped.values_list('unidad_salud', flat=True).exclude(unidad_salud='').distinct().order_by('unidad_salud')
    municipios_list = scoped.values_list('municipio__nombre', flat=True).filter(municipio__isnull=False).distinct().order_by('municipio__nombre')
    estados = scoped.values_list('estado', flat=True).exclude(estado='').distinct().order_by('estado')

    santiago = equipos.filter(municipio__nombre__icontains='Santiago').order_by('unidad_salud', 'denominacion')
    otros = equipos.exclude(municipio__nombre__icontains='Santiago').filter(municipio__isnull=False).order_by('municipio__nombre', 'unidad_salud')
    sin_municipio = equipos.filter(municipio__isnull=True).order_by('unidad_salud')

    hospitales = {}
    for eq in santiago:
        hosp = eq.unidad_salud or 'Sin hospital'
        if hosp not in hospitales:
            hospitales[hosp] = []
        hospitales[hosp].append(eq)

    municipios_agrup = {}
    for eq in otros:
        mun = eq.municipio.nombre if eq.municipio else 'Sin municipio'
        if mun not in municipios_agrup:
            municipios_agrup[mun] = []
        municipios_agrup[mun].append(eq)

    context = {
        'hospitales': hospitales,
        'municipios': municipios_agrup,
        'sin_municipio': sin_municipio,
        'mostrar_departamento': len(ids) > 1,
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


def _equipo_choices(alcanzables, municipios_qs=None):
    import json
    from collections import defaultdict
    ids = [d.pk for d in alcanzables]
    scoped = Equipo.objects.filter(departamento_id__in=ids)
    if municipios_qs is not None:
        scoped = scoped.filter(municipio_id__in=municipios_qs)
    estados = scoped.values_list('estado', flat=True).exclude(estado='').distinct().order_by('estado')
    unidades = list(scoped.values_list('unidad_salud', flat=True).exclude(unidad_salud='').distinct().order_by('unidad_salud'))
    municipios = scoped.values_list('municipio__nombre', flat=True).filter(municipio__isnull=False).distinct().order_by('municipio__nombre')
    mun_unidad = defaultdict(set)
    for eq in scoped.filter(municipio__isnull=False).exclude(unidad_salud='').values('municipio__nombre', 'unidad_salud').distinct():
        mun_unidad[eq['municipio__nombre']].add(eq['unidad_salud'])
    mun_unidad_json = {m: sorted(list(u)) for m, u in mun_unidad.items()}
    return estados, unidades, municipios, json.dumps(mun_unidad_json), json.dumps(unidades)


def equipo_ubicacion(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    equipo = get_object_or_404(Equipo, pk=pk)
    if equipo.departamento_id not in _ids_alcanzables(request):
        return _denegar(request, 'equipo_list')
    return render(request, 'inventario/equipo_ubicacion.html', {
        'equipo': equipo,
    })


def equipo_create(request):
    if not _tiene_sesion(request):
        return redirect('login')
    depto = _departamento_sesion(request)
    departamentos = alcanzar_departamentos(request)
    municipios_qs = _municipios_centro(request)
    if request.method == 'POST':
        form = EquipoForm(request.POST, departamento=depto, departamentos=departamentos, municipios_qs=municipios_qs)
        if form.is_valid():
            destino = form.cleaned_data.get('departamento_destino')
            if destino is None or (depto and destino.pk == depto.pk):
                # Destino = departamento de la sesión: alta directa (P2-D3, UX intacta).
                equipo = form.save(commit=False)
                equipo.departamento = depto or destino
                equipo.save()
                _auditar(request, 'editar', 'Equipo', equipo.pk, f'Creó {equipo}')
                messages.success(request, 'Equipo creado.')
                return redirect('equipo_list')
            # Destino ajeno → SolicitudEquipo pendiente (P2-D3/D7: el dueño aprueba, D8).
            persona = _persona_sesion(request)
            if persona is None:
                messages.error(request, 'Debes iniciar sesión como persona para solicitar un equipo a otro departamento.')
                return redirect('equipo_list')
            datos_snap = {}
            for campo, valor in form.cleaned_data.items():
                if campo == 'departamento_destino':
                    continue
                datos_snap[campo] = valor.pk if hasattr(valor, 'pk') else valor
            SolicitudEquipo.objects.create(
                datos_equipo=datos_snap, departamento_destino=destino, creado_por=persona,
            )
            messages.success(request, f'Solicitud enviada a {destino}. El departamento destino debe aprobarla.')
            return redirect('equipo_list')
    else:
        form = EquipoForm(departamento=depto, departamentos=departamentos, municipios_qs=municipios_qs)
    estados, unidades, municipios, mun_unidad_json, all_unidades_json = _equipo_choices(departamentos, municipios_qs)
    return render(request, 'inventario/equipo_form.html', {
        'form': form, 'crear': True, 'estados': estados,
        'unidades': unidades, 'municipios': municipios,
        'mun_unidad_json': mun_unidad_json,
        'all_unidades_json': all_unidades_json,
    })


def equipo_update(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    equipo = get_object_or_404(Equipo, pk=pk)
    if equipo.departamento_id not in _ids_alcanzables(request):
        return _denegar(request, 'equipo_list')
    if not _mismo_centro(request, equipo):
        return _denegar(request, 'equipo_list')
    depto = _departamento_sesion(request)
    departamentos = alcanzar_departamentos(request)
    es_propio = depto is not None and equipo.departamento_id == depto.pk
    desc = str(equipo)
    if request.method == 'POST':
        form = EquipoForm(request.POST, instance=equipo, departamento=depto, departamentos=departamentos)
        if form.is_valid():
            if es_propio:
                form.save()
                _auditar(request, 'editar', 'Equipo', equipo.pk, desc)
                messages.success(request, 'Equipo actualizado.')
                return redirect('equipo_list')
            # Equipo ajeno: se aplica al instante y queda pendiente de aprobación (D1).
            persona = _persona_sesion(request)
            if persona is None:
                messages.error(request, 'Debes iniciar sesión como persona para editar un equipo de otro departamento.')
                return redirect('equipo_list')
            snapshot = _snapshot_equipo(equipo)
            form.save()
            CambioPendiente.objects.create(
                equipo=equipo, tipo='edicion', snapshot=snapshot,
                solicitado_por=persona, departamento_dueno=equipo.departamento,
            )
            _auditar(request, 'editar', 'Equipo', equipo.pk, desc)
            messages.success(request, 'Cambio aplicado. El departamento dueño debe aprobarlo.')
            return redirect('equipo_list')
    else:
        form = EquipoForm(instance=equipo, departamento=depto, departamentos=departamentos)
    estados, unidades, municipios, mun_unidad_json, all_unidades_json = _equipo_choices(departamentos)
    return render(request, 'inventario/equipo_form.html', {
        'form': form, 'crear': False, 'equipo': equipo,
        'estados': estados, 'unidades': unidades, 'municipios': municipios,
        'mun_unidad_json': mun_unidad_json,
        'all_unidades_json': all_unidades_json,
    })


def equipo_delete(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    equipo = get_object_or_404(Equipo, pk=pk)
    if equipo.departamento_id not in _ids_alcanzables(request):
        return _denegar(request, 'equipo_list')
    if not _mismo_centro(request, equipo):
        return _denegar(request, 'equipo_list')
    depto = _departamento_sesion(request)
    es_propio = depto is not None and equipo.departamento_id == depto.pk
    desc = str(equipo)
    if request.method == 'POST':
        if es_propio:
            # Hard-delete directo sin CambioPendiente (el dueño ya es aprobador, D8).
            _auditar(request, 'eliminar', 'Equipo', equipo.pk, desc)
            Equipo.all_objects.get(pk=equipo.pk).delete()
            messages.success(request, 'Equipo eliminado.')
            return redirect('equipo_list')
        # Equipo ajeno: soft-delete + CambioPendiente (D1/D4: revertir = eliminado_en=None).
        persona = _persona_sesion(request)
        if persona is None:
            messages.error(request, 'Debes iniciar sesión como persona para solicitar la eliminación de un equipo ajeno.')
            return redirect('equipo_list')
        equipo.eliminado_en = timezone.now()
        equipo.save(update_fields=['eliminado_en'])
        CambioPendiente.objects.create(
            equipo=equipo, tipo='eliminacion', snapshot={},
            solicitado_por=persona, departamento_dueno=equipo.departamento,
        )
        _auditar(request, 'eliminar', 'Equipo', equipo.pk, desc)
        messages.success(request, 'Eliminación aplicada. El departamento dueño debe aprobarla.')
        return redirect('equipo_list')
    return render(request, 'inventario/equipo_confirm_delete.html', {'equipo': equipo})


def equipo_duplicados(request):
    if not _tiene_sesion(request):
        return redirect('login')
    ids = _ids_alcanzables(request)
    from django.db.models import Count

    if request.method == 'POST':
        posted = request.POST.getlist('seleccionados')
        if posted:
            eliminados = Equipo.objects.filter(pk__in=posted, departamento_id__in=ids)
            count = eliminados.count()
            desc = ', '.join(str(e) for e in eliminados)
            eliminados.delete()
            _auditar(request, 'eliminar', 'Equipo(s)', 0, f'Eliminados en lote: {desc}')
            messages.success(request, f'{count} equipo(s) eliminado(s).')
        else:
            messages.warning(request, 'No seleccionaste ningún equipo.')
        return redirect('equipo_duplicados')

    dups = Equipo.objects.filter(departamento_id__in=ids).values('numero_serie').exclude(numero_serie='').annotate(
        count=Count('id')
    ).filter(count__gt=1).order_by('-count')

    grupos = []
    for d in dups:
        equipos = Equipo.objects.filter(numero_serie=d['numero_serie'], departamento_id__in=ids)
        grupos.append({
            'numero_serie': d['numero_serie'],
            'count': d['count'],
            'equipos': equipos,
        })

    return render(request, 'inventario/equipo_duplicados.html', {
        'grupos': grupos,
        'total_duplicados': len(grupos),
    })


def equipo_estadisticas(request):
    if not _tiene_sesion(request):
        return redirect('login')
    # Alcance territorial: SOLO los equipos de los municipios que atiende el
    # centro (igual que equipo_list), no todos los del departamento padre.
    equipos = _equipos_visibles(request)
    total = equipos.count()

    def pct(n):
        return round(n * 100 / total, 1) if total else 0

    estados = {}
    for fila in equipos.values('estado').annotate(n=Count('id')).order_by('-n'):
        raw = fila['estado'] or ''
        cnt = fila['n']
        nombre = raw if raw.strip() else 'Sin estado'
        if nombre.upper() == 'ROTO':
            nombre = 'Roto'
        estados[nombre] = estados.get(nombre, 0) + cnt
    estados = sorted(estados.items(), key=lambda kv: -kv[1])

    municipios = [
        {'municipio': m['municipio__nombre'], 'total': m['n'], 'pct': pct(m['n'])}
        for m in equipos.exclude(municipio__isnull=True).values('municipio__nombre').annotate(n=Count('id')).order_by('-n')[:10]
    ]

    tipos = {}
    labels = dict(Equipo.TIPO_CHOICES)
    for fila in equipos.values('tipo').annotate(n=Count('id')).order_by('-n'):
        nombre = labels.get(fila['tipo'], fila['tipo'] or 'Sin tipo')
        tipos[nombre] = tipos.get(nombre, 0) + fila['n']
    tipos = sorted(tipos.items(), key=lambda kv: -kv[1])

    colores_estado = {
        'Funcionando': 'bg-success',
        'Afectado': 'bg-warning',
        'Roto': 'bg-danger',
        'Fuera de servicio': 'bg-secondary',
        'Pendiente': 'bg-info',
        'Sin estado': 'bg-dark',
    }

    return render(request, 'inventario/equipo_estadisticas.html', {
        'total': total,
        'estados': [{'nombre': n, 'total': c, 'pct': pct(c), 'color': colores_estado.get(n, 'bg-primary')} for n, c in estados],
        'municipios': municipios,
        'tipos': [{'nombre': n, 'total': c, 'pct': pct(c)} for n, c in tipos],
    })


def periodo_list(request):
    if not _tiene_sesion(request):
        return redirect('login')
    periodos = Periodo.objects.all()
    return render(request, 'inventario/periodo_list.html', {
        'periodos': periodos,
    })


def periodo_create(request):
    if not _tiene_sesion(request):
        return redirect('login')
    if request.method == 'POST':
        fi = request.POST.get('fecha_inicio', '')
        ff = request.POST.get('fecha_fin', '')
        if fi and ff:
            try:
                inicio = datetime.strptime(fi, '%Y-%m-%d').date()
                fin = datetime.strptime(ff, '%Y-%m-%d').date()
                if fin < inicio:
                    messages.error(request, 'La fecha fin no puede ser anterior a la fecha inicio.')
                    return render(request, 'inventario/periodo_form.html', {'inicio': fi, 'fin': ff})
                Periodo.objects.create(fecha_inicio=inicio, fecha_fin=fin)
                messages.success(request, f'Periodo {inicio:%d/%m/%Y} – {fin:%d/%m/%Y} creado.')
                return redirect('dashboard')
            except (ValueError, TypeError):
                messages.error(request, 'Fechas inválidas.')
        else:
            messages.error(request, 'Ambas fechas son requeridas.')
    return render(request, 'inventario/periodo_form.html')


def periodo_delete(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    periodo = get_object_or_404(Periodo, pk=pk)

    if request.method == 'POST':
        partes = ParteTrabajo.objects.filter(
            fecha_inicio__gte=periodo.fecha_inicio, fecha_fin__lte=periodo.fecha_fin
        )
        cant_partes = partes.count()
        partes.delete()

        asignaciones = Asignacion.objects.filter(
            fecha__gte=periodo.fecha_inicio, fecha__lte=periodo.fecha_fin
        )
        cant_asig = asignaciones.count()
        asignaciones.delete()

        OrdenTrabajo.objects.filter(~Q(asignaciones__pk__isnull=False)).delete()
        periodo.delete()

        messages.success(
            request,
            f'Periodo {periodo.fecha_inicio:%d/%m/%Y} – {periodo.fecha_fin:%d/%m/%Y} eliminado: '
            f'{cant_partes} parte(s) y {cant_asig} asignacion(es).'
        )
        return redirect('dashboard')

    return render(request, 'inventario/periodo_confirm_delete.html', {
        'periodo': periodo,
    })


def historial(request):
    if not _tiene_sesion(request):
        return redirect('login')
    if request.user.is_staff:
        logs = Auditoria.objects.select_related('usuario').all()
    else:
        logs = Auditoria.objects.select_related('usuario').filter(
            usuario__departamento_id__in=_ids_alcanzables(request)
        )
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


def admin_panel(request):
    if not request.user.is_superuser:
        return redirect('login')
    enlaces = VisitaLink.objects.all()
    return render(request, 'inventario/admin_panel.html', {
        'enlaces': enlaces,
    })


def generar_enlace(request):
    if not request.user.is_superuser:
        return redirect('login')
    if request.method == 'POST':
        VisitaLink.objects.create(creado_por=request.user)
        messages.success(request, 'Enlace de visita generado.')
    return redirect('admin_panel')


def eliminar_enlace(request, pk):
    if not request.user.is_superuser:
        return redirect('login')
    enlace = get_object_or_404(VisitaLink, pk=pk)
    if request.method == 'POST':
        enlace.delete()
        messages.success(request, 'Enlace eliminado.')
    return redirect('admin_panel')


def visitar_entrar(request, uuid_code):
    enlace = get_object_or_404(VisitaLink, uuid=uuid_code)
    if enlace.usado:
        messages.error(request, 'Este enlace de visita ya fue usado.')
        return redirect('login')
    if request.user.is_authenticated:
        auth_logout(request)
        for key in ['persona_id', 'persona_nombre']:
            request.session.pop(key, None)
    enlace.usado = True
    enlace.fecha_uso = timezone.now()
    enlace.save(update_fields=['usado', 'fecha_uso'])
    request.session['is_visitor'] = True
    request.session['visitor_link_id'] = enlace.pk
    request.session.save()
    messages.info(request, 'Modo visita — solo puedes ver la información, no editarla.')
    return redirect('dashboard')


@xframe_options_sameorigin
def visitar(request, uuid_code):
    enlace = get_object_or_404(VisitaLink, uuid=uuid_code)
    if enlace.usado:
        messages.error(request, 'Este enlace de visita ya fue usado.')
        return redirect('login')
    return render(request, 'inventario/visitar_confirm.html', {
        'enlace': enlace,
        'action': reverse('visitar_entrar', args=[uuid_code]),
    })


def exit_visitor(request):
    for key in ['is_visitor', 'visitor_link_id', 'persona_id', 'persona_nombre']:
        request.session.pop(key, None)
    messages.info(request, 'Has salido del modo visita.')
    return redirect('login')


# ---------------------------------------------------------------------------
# Jerarquía de centros territoriales (Fase 3): solicitudes, cambios y centros
# ---------------------------------------------------------------------------

def _solicitudes_pendientes_qs(request):
    """Solicitudes cuyo departamento_destino es alcanzable por la sesión actual."""
    depto = _departamento_sesion(request)
    qs = SolicitudEquipo.objects.filter(estado='pendiente')
    if depto is not None:
        qs = qs.filter(departamento_destino_id__in=_ids_alcanzables(request))
    return qs.order_by('-fecha_creacion')


def _cambios_pendientes_qs(request):
    """Cambios pendientes de equipos cuyo departamento dueño es alcanzable."""
    depto = _departamento_sesion(request)
    qs = CambioPendiente.objects.filter(estado='pendiente')
    if depto is not None:
        qs = qs.filter(departamento_dueno_id__in=_ids_alcanzables(request))
    return qs.order_by('-fecha_creacion')


def solicitud_list(request):
    if not _tiene_sesion(request):
        return redirect('login')
    depto = _departamento_sesion(request)
    context = {'solicitudes': _solicitudes_pendientes_qs(request)}
    if depto is not None:
        context['cambios'] = _cambios_pendientes_qs(request)
    return render(request, 'inventario/solicitud_list.html', context)


def solicitud_create(request):
    if not _tiene_sesion(request):
        return redirect('login')
    depto = _departamento_sesion(request)
    departamentos = alcanzar_departamentos(request)
    municipios_qs = _municipios_centro(request)
    if request.method == 'POST':
        form = SolicitudEquipoForm(request.POST, departamento=depto, departamentos=departamentos, municipios_qs=municipios_qs)
        if form.is_valid():
            destino = form.cleaned_data['departamento_destino']
            persona = _persona_sesion(request)
            if persona is None:
                messages.error(request, 'Debes iniciar sesión como persona para enviar una solicitud.')
                return redirect('equipo_list')
            SolicitudEquipo.objects.create(
                datos_equipo=form.snapshot(),
                departamento_destino=destino,
                creado_por=persona,
            )
            _auditar(request, 'editar', 'Equipo', 0, f'Solicitud de equipo a {destino} por {persona}')
            messages.success(request, f'Solicitud enviada a {destino}.')
            return redirect('solicitud_list')
    else:
        form = SolicitudEquipoForm(departamento=depto, departamentos=departamentos, municipios_qs=municipios_qs)
    return render(request, 'inventario/solicitud_form.html', {'form': form})


def solicitud_aprobar(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    solicitud = get_object_or_404(SolicitudEquipo, pk=pk)
    if solicitud.estado != 'pendiente':
        messages.error(request, 'La solicitud ya fue procesada.')
        return redirect('solicitud_list')
    depto = _departamento_sesion(request)
    if depto is None or solicitud.departamento_destino_id not in _ids_alcanzables(request):
        return _denegar(request, 'solicitud_list')
    if request.method == 'POST':
        datos = solicitud.datos_equipo
        # D8: el equipo nace con el departamento_destino al aprobarse.
        equipo = Equipo(
            departamento_id=datos.get('departamento') or solicitud.departamento_destino_id,
            municipio_id=datos.get('municipio'),
            unidad_salud=datos.get('unidad_salud'),
            tipo=datos.get('tipo'), denominacion=datos.get('denominacion'),
            servicio=datos.get('servicio'), local=datos.get('local'),
            marca=datos.get('marca'), modelo=datos.get('modelo'),
            numero_serie=datos.get('numero_serie'), estado=datos.get('estado'),
            observaciones=datos.get('observaciones'), frecuencia=datos.get('frecuencia'),
            fuente=datos.get('fuente'),
            ubicacion_temporal_municipio=datos.get('ubicacion_temporal_municipio'),
            ubicacion_temporal_unidad=datos.get('ubicacion_temporal_unidad'),
            nota_interna=datos.get('nota_interna'),
        )
        equipo.save()
        solicitud.estado = 'aprobado'
        solicitud.save(update_fields=['estado'])
        _auditar(request, 'editar', 'Equipo', equipo.pk,
                 f'Aprobó solicitud de {solicitud.creado_por} ({solicitud.departamento_destino})')
        messages.success(request, 'Solicitud aprobada. Equipo creado.')
        return redirect('solicitud_list')
    return render(request, 'inventario/solicitud_confirm.html', {
        'solicitud': solicitud,
        'action': reverse('solicitud_aprobar', args=[pk]),
    })


def solicitud_cancelar(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    solicitud = get_object_or_404(SolicitudEquipo, pk=pk)
    if solicitud.estado != 'pendiente':
        messages.error(request, 'La solicitud ya fue procesada.')
        return redirect('solicitud_list')
    depto = _departamento_sesion(request)
    if depto is None or solicitud.departamento_destino_id not in _ids_alcanzables(request):
        return _denegar(request, 'solicitud_list')
    if request.method == 'POST':
        solicitud.estado = 'cancelado'
        solicitud.save(update_fields=['estado'])
        messages.success(request, 'Solicitud cancelada.')
        return redirect('solicitud_list')
    return render(request, 'inventario/solicitud_confirm.html', {
        'solicitud': solicitud,
        'action': reverse('solicitud_cancelar', args=[pk]),
    })


def cambio_aprobar(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    cambio = get_object_or_404(CambioPendiente, pk=pk)
    if cambio.estado != 'pendiente':
        messages.error(request, 'El cambio ya fue procesado.')
        return redirect('solicitud_list')
    depto = _departamento_sesion(request)
    if depto is None or (cambio.departamento_dueno_id and cambio.departamento_dueno_id not in _ids_alcanzables(request)):
        return _denegar(request, 'solicitud_list')
    if request.method == 'POST':
        if cambio.tipo == 'eliminacion' and cambio.equipo is not None:
            cambio.equipo.eliminado_en = timezone.now()
            cambio.equipo.save(update_fields=['eliminado_en'])
        cambio.estado = 'aprobado'
        cambio.save(update_fields=['estado'])
        _auditar(request, 'editar', 'Equipo', cambio.equipo_id or 0, f'Aprobó cambio ({cambio.tipo}) de {cambio.solicitado_por}')
        messages.success(request, 'Cambio aprobado.')
        return redirect('solicitud_list')
    return render(request, 'inventario/cambio_confirm.html', {
        'cambio': cambio,
        'action': reverse('cambio_aprobar', args=[pk]),
    })


def cambio_cancelar(request, pk):
    if not _tiene_sesion(request):
        return redirect('login')
    cambio = get_object_or_404(CambioPendiente, pk=pk)
    if cambio.estado != 'pendiente':
        messages.error(request, 'El cambio ya fue procesado.')
        return redirect('solicitud_list')
    depto = _departamento_sesion(request)
    if depto is None or (cambio.departamento_dueno_id and cambio.departamento_dueno_id not in _ids_alcanzables(request)):
        return _denegar(request, 'solicitud_list')
    if request.method == 'POST':
        if cambio.tipo == 'eliminacion' and cambio.equipo is not None:
            cambio.equipo.eliminado_en = None
            cambio.equipo.save(update_fields=['eliminado_en'])
        elif cambio.tipo == 'edicion' and cambio.equipo is not None and cambio.snapshot:
            _restaurar_snapshot(cambio.equipo, cambio.snapshot)
        cambio.estado = 'cancelado'
        cambio.save(update_fields=['estado'])
        _auditar(request, 'editar', 'Equipo', cambio.equipo_id or 0, f'Rechazó cambio ({cambio.tipo}) de {cambio.solicitado_por}')
        messages.success(request, 'Cambio rechazado. Se restauró el estado anterior.')
        return redirect('solicitud_list')
    return render(request, 'inventario/cambio_confirm.html', {
        'cambio': cambio,
        'action': reverse('cambio_cancelar', args=[pk]),
    })


def centro_list(request):
    if not request.user.is_staff:
        return redirect('login')
    centros = Centro.objects.all().order_by('tipo', 'nombre')
    return render(request, 'inventario/centro_list.html', {'centros': centros})


def centro_create(request):
    if not request.user.is_staff:
        return redirect('login')
    if request.method == 'POST':
        form = CentroForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Centro creado.')
            return redirect('centro_list')
    else:
        form = CentroForm()
    return render(request, 'inventario/centro_form.html', {'form': form})


def centro_edit(request, pk):
    if not request.user.is_staff:
        return redirect('login')
    centro = get_object_or_404(Centro, pk=pk)
    if request.method == 'POST':
        form = CentroForm(request.POST, instance=centro)
        if form.is_valid():
            form.save()
            messages.success(request, f'Centro {centro.nombre} actualizado.')
            return redirect('centro_list')
    else:
        form = CentroForm(instance=centro)
    return render(request, 'inventario/centro_form.html', {'form': form, 'centro': centro})


def centro_contrasenas(request):
    """Sesión territorial: gestiona las contraseñas LOCALES que sus departamentos
    (los del centro padre) usan para entrar a SU centro."""
    if not _tiene_sesion(request):
        return redirect('login')
    centro_pk = request.session.get('centro_territorial_pk')
    if not centro_pk:
        return _denegar(request, 'dashboard')
    centro = get_object_or_404(Centro, pk=centro_pk)
    if centro.tipo != 'territorial' or not centro.centro_padre_id:
        return _denegar(request, 'dashboard')
    departamentos = Departamento.objects.filter(
        centro_id=centro.centro_padre_id, activo=True,
    ).order_by('nombre')
    if request.method == 'POST':
        depto_pk = request.POST.get('departamento_pk')
        form = DepartamentoCentroForm(request.POST)
        departamento = departamentos.filter(pk=depto_pk).first()
        if departamento and form.is_valid():
            local, _ = DepartamentoCentro.objects.update_or_create(
                departamento=departamento, centro=centro,
                defaults={'contrasena': make_password(form.cleaned_data['contrasena'])},
            )
            _auditar(request, 'editar', 'Centro', centro.pk,
                     f'Contraseña local de {departamento} en centro territorial {centro.nombre}')
            messages.success(request, f'Contraseña local de {departamento} actualizada.')
        else:
            messages.error(request, 'No se pudo actualizar la contraseña.')
        return redirect('centro_contrasenas')
    locales = {
        dc.departamento_id: dc
        for dc in DepartamentoCentro.objects.filter(centro=centro)
    }
    return render(request, 'inventario/centro_contrasenas.html', {
        'centro': centro,
        'departamentos': departamentos,
        'locales': locales,
        'form': DepartamentoCentroForm(),
    })


def municipio_create(request):
    if not request.user.is_staff:
        return redirect('login')
    if request.method == 'POST':
        form = MunicipioForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Municipio creado.')
            return redirect('municipio_list')
    else:
        form = MunicipioForm()
    return render(request, 'inventario/municipio_form.html', {'form': form})


def municipio_list(request):
    if not request.user.is_staff:
        return redirect('login')
    municipios = Municipio.objects.select_related('centro').order_by('centro__nombre', 'nombre')
    return render(request, 'inventario/municipio_list.html', {'municipios': municipios})