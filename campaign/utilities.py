from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from functools import wraps

def restrict_access(allowed_roles=None, redirect_url="main_page"):
    allowed_roles = allowed_roles or []

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("main_page") 
            if request.user.role not in allowed_roles:
                if redirect_url:
                    return redirect(redirect_url)
                return HttpResponseForbidden("You do not have access to this resource.")
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
