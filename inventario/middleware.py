from django.shortcuts import redirect
from django.contrib import messages


class VisitorModeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.session.get('is_visitor') and request.method == 'POST':
            path = request.path
            allowed_paths = ['/login/', '/logout/']
            if not any(path.startswith(p) for p in allowed_paths):
                messages.error(request, 'No puedes modificar datos en modo visita.')
                return redirect(request.META.get('HTTP_REFERER', 'dashboard'))
        return self.get_response(request)
