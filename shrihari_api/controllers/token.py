from odoo.http import  Response, request
import json
import logging
from datetime import datetime

_logger = logging.getLogger(__name__)

def validate_partner_token(request, user_id):
        # _logger.info("Validating partner token... %s", user_id or 'N/A')
        # Get Authorization Header
        auth_header = request.httprequest.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return None, "Missing or invalid token format"

        token = auth_header.split(' ')[1]
        user = request.env['res.users'].sudo().search([
            ('id', '=', user_id),
            ('active', '=', True)
        ], limit=1)
        # _logger.info("User found: %s", user)

        api_key_record = request.env['partner.api.key'].sudo().search([
            ('user_id', '=',user.id),
            ('api_key', '=', token),
            ('expiry_date', '>=', datetime.now())
        ], limit=1)

        # _logger.info("API Key Record: %s", api_key_record)

        if not api_key_record:
            return None, "Token is Expired"
        return api_key_record.user_id, None

def validate_api_request(request, kwargs):
        """ Common function for user_id + token validation """
        user_id = kwargs.get('user_id')

        if not user_id:
            return None, Response(json.dumps({
                "success": False,
                "message": "user_id (user_id) is required"
            }), content_type='application/json')
            
        # :white_tick: Validate token
        user, error = validate_partner_token(request, user_id)
        # _logger.warning(f"[API] Token validation failed: {error}")
        if error:
            return None, Response(json.dumps({
                "success": False,
                "message": error
            }), content_type='application/json')
        # _logger.info(f"Token validated for user: {user.id} - {user.name}")
        return user, None

