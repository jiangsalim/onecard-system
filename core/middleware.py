from django.shortcuts import render
from django.http import JsonResponse
from django.core.cache import cache
import logging
import ipaddress
import time

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
        '/login/': (10, 300),           # 10 attempts per 5 minutes
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
                    
                    # For API requests, return JSON
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'success': False,
                            'error': 'Too many requests. Please slow down.',
                            'error_code': 'RATE_LIMITED',
                            'retry_after': window
                        }, status=429)
                    
                    # For login page, set a flag that the view will check
                    request.rate_limited = True
                    request.rate_limit_retry_after = window
                    # Still let the request through — the view handles the UI
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