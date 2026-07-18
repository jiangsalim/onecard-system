from django.shortcuts import render
from django.http import JsonResponse
from django.core.cache import cache
import logging
import ipaddress
import time
from datetime import datetime, timedelta

logger = logging.getLogger('onecard')


class ErrorHandlerMiddleware:
    """Global error handling middleware."""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        return response
    
    def process_exception(self, request, exception):
        """Handle unhandled exceptions."""
        logger.error(f"Unhandled error: {str(exception)}", exc_info=True)
        
        if request.path.startswith('/api/'):
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.',
                'error_code': 'SERVER_ERROR'
            }, status=500)
        
        return render(request, 'errors/500.html', status=500)


class RateLimitMiddleware:
    """Rate limiting middleware with login page countdown support."""
    
    RATE_LIMITS = {
        '/api/scan/': (60, 60),
        '/login/': (30, 300),           # 30 attempts per 5 minutes
        '/api/pass-out/': (30, 60),
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        ip = self.get_client_ip(request)
        
        for path_prefix, (max_requests, window) in self.RATE_LIMITS.items():
            if request.path.startswith(path_prefix):
                cache_key = f'ratelimit_{path_prefix}_{ip}'
                requests_count = cache.get(cache_key, 0)
                
                if requests_count >= max_requests:
                    logger.warning(f"Rate limit exceeded: {ip} on {path_prefix}")
                    
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'success': False,
                            'error': 'Too many requests. Please slow down.',
                            'error_code': 'RATE_LIMITED',
                            'retry_after': window
                        }, status=429)
                    
                    request.rate_limited = True
                    request.rate_limit_retry_after = window
                    return self.get_response(request)
                
                cache.set(cache_key, requests_count + 1, window)
                break
        
        return self.get_response(request)
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0].strip()
        else:
            ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
        return ip


class AccountLockoutMiddleware:
    """Lock account after 5 failed login attempts for 15 minutes."""
    
    MAX_FAILURES = 5
    LOCKOUT_MINUTES = 15
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method == 'POST' and request.path == '/login/':
            username = request.POST.get('username', '')
            
            if username:
                lockout_key = f'lockout_{username}'
                locked_until = cache.get(lockout_key)
                
                if locked_until:
                    remaining = max(int((locked_until - datetime.now()).total_seconds() // 60), 1)
                    logger.warning(f"Blocked login attempt for locked account: {username}")
                    
                    from django.contrib import messages
                    messages.error(
                        request,
                        f'Account temporarily locked due to too many failed attempts. Try again in {remaining} minute(s).'
                    )
                    
                    from core.mobile_utils import render_mobile_or_desktop
                    return render_mobile_or_desktop(
                        request, 'auth/login.html', 'mobile/login.html',
                        {'rate_limited': True, 'retry_after': max(remaining * 60, 60)}
                    )
        
        return self.get_response(request)


def record_failed_login(username):
    """Record a failed login attempt. Returns True if account is now locked."""
    failed_key = f'login_failed_{username}'
    lockout_key = f'lockout_{username}'
    
    failures = cache.get(failed_key, 0) + 1
    cache.set(failed_key, failures, 900)
    
    if failures >= AccountLockoutMiddleware.MAX_FAILURES:
        cache.set(
            lockout_key,
            datetime.now() + timedelta(minutes=AccountLockoutMiddleware.LOCKOUT_MINUTES),
            900
        )
        logger.warning(f"ACCOUNT LOCKED: {username} after {failures} failed attempts")
        return True
    
    return False


def reset_failed_logins(username):
    """Reset failed login counter on successful login."""
    cache.delete(f'login_failed_{username}')
    cache.delete(f'lockout_{username}')


class IPRestrictionMiddleware:
    """Restrict sensitive paths to local network only."""
    
    LOCAL_NETWORKS = [
        ipaddress.ip_network('192.168.0.0/16'),
        ipaddress.ip_network('10.0.0.0/8'),
        ipaddress.ip_network('172.16.0.0/12'),
        ipaddress.ip_network('127.0.0.0/8'),
    ]
    
    RESTRICTED_PATHS = ['/admin/', '/dashboard/', '/api/']
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        from django.conf import settings
        
        if settings.DEBUG:
            return self.get_response(request)
        
        is_restricted = any(request.path.startswith(p) for p in self.RESTRICTED_PATHS)
        
        if is_restricted:
            client_ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
            
            try:
                ip = ipaddress.ip_address(client_ip)
                is_local = any(ip in net for net in self.LOCAL_NETWORKS)
            except ValueError:
                is_local = True
            
            if not is_local:
                logger.warning(f"IP restriction: Blocked {client_ip} from {request.path}")
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden("Access restricted to school network only.")
        
        return self.get_response(request)
    

class SessionSecurityMiddleware:
    """Bind session to original IP and User-Agent. Prevents session hijacking."""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            current_ip = request.META.get('REMOTE_ADDR')
            current_ua = request.META.get('HTTP_USER_AGENT', '')[:200]
            
            session_ip = request.session.get('bound_ip')
            session_ua = request.session.get('bound_ua')
            
            if session_ip is None:
                request.session['bound_ip'] = current_ip
                request.session['bound_ua'] = current_ua
            elif session_ip != current_ip or session_ua != current_ua:
                from django.contrib.auth import logout
                logger.warning(
                    f"Session security: IP/UA mismatch for {request.user.username}. "
                    f"Original IP: {session_ip}, New IP: {current_ip}"
                )
                logout(request)
                from django.shortcuts import redirect
                return redirect('login')
        
        return self.get_response(request)