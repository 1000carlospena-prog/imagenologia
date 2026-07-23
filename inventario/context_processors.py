from .models import Persona, Periodo


def persona_actual(request):
    persona_id = request.session.get('persona_id')
    try:
        persona = Persona.objects.get(pk=persona_id) if persona_id else None
    except Persona.DoesNotExist:
        persona = None
    return {'persona_actual': persona}


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
