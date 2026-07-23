from .models import Persona


def persona_actual(request):
    persona_id = request.session.get('persona_id')
    try:
        persona = Persona.objects.get(pk=persona_id) if persona_id else None
    except Persona.DoesNotExist:
        persona = None
    return {'persona_actual': persona}
