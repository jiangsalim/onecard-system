from functools import wraps
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import authenticate
from django.utils import timezone


def reauth_required(view_func):
    """Require password re-entry for sensitive actions (5 minute window)."""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        last_auth = request.session.get('last_auth')
        now = timezone.now().timestamp()
        
        # Check if re-auth is needed
        if not last_auth or (now - last_auth) > 300:  # 5 minutes
            if request.method == 'POST' and 'reauth_password' in request.POST:
                user = authenticate(
                    request,
                    username=request.user.username,
                    password=request.POST['reauth_password']
                )
                if user is not None:
                    request.session['last_auth'] = int(now)
                    return view_func(request, *args, **kwargs)
                else:
                    messages.error(request, 'Incorrect password. Please try again.')
            
            # Show re-auth form
            return render(request, 'auth/reauth.html', {
                'action_url': request.path,
                'action_name': view_func.__name__.replace('_', ' ').title(),
            })
        
        # Already authenticated — proceed
        return view_func(request, *args, **kwargs)
    return wrapper