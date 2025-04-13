from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

class DisableCacheMiddleware(MiddlewareMixin):
    """
    Middleware to:
    - Prevent caching for all pages.
    - Handle HTTP errors with a custom error template.
    """
    def process_request(self, request):
        """
        Handle incoming requests. Add necessary cache headers for all requests.
        """
        logger.debug(f"Processing request for path: {request.path}")
        request.META['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        request.META['Pragma'] = 'no-cache'
        request.META['Expires'] = '0'

    def process_response(self, request, response):
        """
        Handle outgoing responses. Add cache control headers and custom error handling.
        """
        # Apply cache headers to all responses
        response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'

        # Handle specific error codes with a custom error template
        error_status_codes = [
            400, 401, 403, 404, 405, 408, 409, 410, 411, 412, 413,
            414, 415, 416, 417, 418, 429, 500, 501, 502, 503, 504, 505
        ]

        if response.status_code in error_status_codes:
            logger.debug(f"Handling error with status code: {response.status_code}")
            return self.handle_error(request, response.status_code)

        return response

    def handle_error(self, request, status_code):
        """
        Render a custom error template with the status code.
        """
        logger.error(f"Error detected: {status_code} for path: {request.path}")
        context = {'status_code': status_code}
        return render(request, 'campaign/error_template.html', context, status=status_code)
