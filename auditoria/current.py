from contextvars import ContextVar

_current_user = ContextVar("audit_user", default=None)


def set_user(user):
    return _current_user.set(user)


def reset(token):
    _current_user.reset(token)


def get_user():
    user = _current_user.get()
    return user if user is not None and user.is_authenticated else None


class CurrentUserMiddleware:
    """Guarda o usuário da requisição para que os registros do histórico saibam quem agiu."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = set_user(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            reset(token)
