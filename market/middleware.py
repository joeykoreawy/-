class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.path == '/admin/login/':
            from .security import limited
            from .views import error
            if limited(request, 'admin-login-ip', 60, 900) or limited(request, 'admin-login-name', 12, 900, request.POST.get('username', '').lower()):
                return error(request, '로그인 시도가 많습니다. 15분 후 다시 시도해 주세요.', 429)
        response = self.get_response(request)
        # Authenticated HTML and contact details must not enter shared caches.
        if not request.path.startswith('/static/'):
            response['Cache-Control'] = 'no-store, private'
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
        response['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        return response
