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
        
        # For API requests, return JSON
        if request.path.startswith('/api/'):
            return JsonResponse({
                'success': False,
                'error': 'An unexpected error occurred. Please try again.',
                'error_code': 'SERVER_ERROR'
            }, status=500)
        
        # For web requests, render error page
        return render(request, 'errors/500.html', status=500)


class RateLimitMiddleware:
    """Simple rate limiting middleware based on IP address."""
    
    # Format: path_prefix: (max_requests, window_seconds)
    RATE_LIMITS = {
        '/api/scan/': (30, 60),         # 30 scans per minute
        '/login/': (5, 900),            # 5 login attempts per 15 minutes
        '/api/pass-out/': (15, 60),     # 15 pass-outs per minute
    }
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        ip = self.get_client_ip(request)
        
        for path_prefix, (max_requests, window) in self.RATE_LIMITS.items():
            if request.path.startswith(path_prefix):
                cache_key = f'ratelimit_{path_prefix}_{ip}'
                requests = cache.get(cache_key, 0)
                
                if requests >= max_requests:
                    logger.warning(f"Rate limit exceeded: {ip} on {path_prefix}")
                    if request.path.startswith('/api/'):
                        return JsonResponse({
                            'success': False,
                            'error': 'Too many requests. Please slow down.',
                            'error_code': 'RATE_LIMITED',
                            'retry_after': window
                        }, status=429)
                    return JsonResponse({'error': 'Rate limited'}, status=429)
                
                # Increment counter with expiry
                cache.set(cache_key, requests + 1, window)
                break
        
        return self.get_response(request)
    
    def get_client_ip(self, request):
        """Extract client IP from request."""
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
        
        # Allow all in development mode
        if settings.DEBUG:
            return self.get_response(request)
        
        # Check if path is restricted
        is_restricted = any(request.path.startswith(p) for p in self.RESTRICTED_PATHS)
        
        if is_restricted:
            client_ip = request.META.get('REMOTE_ADDR', '127.0.0.1')
            
            try:
                ip = ipaddress.ip_address(client_ip)
                is_local = any(ip in net for net in self.LOCAL_NETWORKS)
            except ValueError:
                is_local = True  # Allow if IP can't be parsed
            
            if not is_local:
                logger.warning(f"IP restriction: Blocked {client_ip} from {request.path}")
                from django.http import HttpResponseForbidden
                return HttpResponseForbidden(
                    "Access restricted to school network only."
                )
        
        return self.get_response(request)