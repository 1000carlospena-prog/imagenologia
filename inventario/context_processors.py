from .models import Departamento, Persona, Periodo, get_configuracion, SolicitudEquipo, CambioPendiente


def persona_actual(request):
    persona_id = request.session.get('persona_id')
    is_visitor = request.session.get('is_visitor', False)
    try:
        persona = Persona.objects.get(pk=persona_id) if persona_id else None
    except Persona.DoesNotExist:
        persona = None
    departamento_id = request.session.get('departamento_pk')
    departamento = None
    if departamento_id:
        try:
            departamento = Departamento.objects.get(pk=departamento_id)
        except Departamento.DoesNotExist:
            departamento = None
    return {
        'persona_actual': persona,
        'is_visitor': is_visitor,
        'departamento_actual': departamento,
    }


def periodo_activo(request):
    periodos = Periodo.objects.all()
    pk = request.session.get('periodo_pk')
    if pk:
        try:
            periodo = Periodo.objects.get(pk=pk)
        except Periodo.DoesNotExist:
            periodo = periodos.first()
    else:
        periodo = periodos.first()
    return {'periodos': periodos, 'periodo_activo': periodo}


def configuracion_global(request):
    """P3-D1: expone la configuración y los contadores de aprobaciones pendientes
    (alcance de la sesión: centro_territorial_pk o departamento)."""
    config = get_configuracion()
    departamento_id = request.session.get('departamento_pk')
    centro_pk = request.session.get('centro_territorial_pk')
    solicitudes_pendientes = cambios_pendientes = 0
    if request.user.is_staff or request.session.get('is_visitor'):
        solicitudes_pendientes = SolicitudEquipo.objects.filter(estado='pendiente').count()
        cambios_pendientes = CambioPendiente.objects.filter(estado='pendiente').count()
    elif departamento_id:
        if centro_pk:
            departamentos_ids = Departamento.objects.filter(centro_id=centro_pk).values_list('pk', flat=True)
            solicitudes_pendientes = SolicitudEquipo.objects.filter(
                estado='pendiente', departamento_destino_id__in=departamentos_ids).count()
            cambios_pendientes = CambioPendiente.objects.filter(
                estado='pendiente', departamento_dueno_id__in=departamentos_ids).count()
        else:
            solicitudes_pendientes = SolicitudEquipo.objects.filter(
                estado='pendiente', departamento_destino_id=departamento_id).count()
            cambios_pendientes = CambioPendiente.objects.filter(
                estado='pendiente', departamento_dueno_id=departamento_id).count()
    return {
        'configuracion_global': config,
        'solicitudes_pendientes': solicitudes_pendientes,
        'cambios_pendientes': cambios_pendientes,
    }
