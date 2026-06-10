from django.shortcuts import render
from django.http import JsonResponse
import logging

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