"""
Mobile device detection for OneCard System.
Detects phones based on User-Agent AND screen width cookie.
"""
from django.shortcuts import render


def is_mobile_device(request):
    """Detect if the request is from a mobile phone."""
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    mobile_patterns = [
        'Mobile', 'Android', 'iPhone', 'iPod',
        'BlackBerry', 'Windows Phone', 'Opera Mini',
        'IEMobile', 'webOS',
    ]

    # Check User-Agent
    if any(pattern in user_agent for pattern in mobile_patterns):
        if 'Android' in user_agent and 'Mobile' not in user_agent:
            return False  # Tablet
        return True  # Phone

    # Check screen width cookie
    screen_width = request.COOKIES.get('screen_width')
    if screen_width:
        try:
            if int(screen_width) <= 768:
                return True
        except (ValueError, TypeError):
            pass

    return False


def render_mobile_or_desktop(request, desktop_template, mobile_template, context=None):
    """Render the appropriate template based on device."""
    if context is None:
        context = {}

    if is_mobile_device(request):
        return render(request, mobile_template, context)
    return render(request, desktop_template, context)