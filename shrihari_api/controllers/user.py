from odoo.http import request, Response
from odoo import http
import json
from datetime import datetime , timedelta
import secrets
from .token import validate_api_request
import logging
_logger = logging.getLogger(__name__)


class UserController(http.Controller):
    
    @http.route('/user_login', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def user_login(self, **kwargs):
        email = kwargs.get('email')
        password = kwargs.get('password')
        device_token = kwargs.get('device_token')
        # credential = {'login': email, 'password': password, 'type': 'password'}

        _logger.info("Login attempt with email: %s", email)

        if not email or not password:
            return Response(json.dumps({
                'success': False,
                'message': 'Email and password are required!',
            }), content_type='application/json')

        #  Search for the user
        user = request.env['res.users'].sudo().search([
            ('login', '=', email),
            ('active', '=', True)
        ], limit=1)
        _logger.info("this is user %s", user)
        if not user:
            inactive_user = request.env['res.users'].sudo().search([
                ('login', '=', email),
                ('active', '=', False)
            ], limit=1)
            if inactive_user:
                _logger.warning("User found but account is deactivated: %s", email)
                return Response(json.dumps({
                    'success': False,
                    'message': 'Account deactivated, please contact support!',
                }), content_type='application/json')
            else:
                return Response(json.dumps({
                    'success': False,
                    'message': 'Email not found!',
                }), content_type='application/json')

        try:
            # Check password inside try block
            user_env = request.env(user=user)
            credential = {'login': email, 'password': password, 'type': 'password'}
            uid=user_env.user._check_credentials(credential, user_env)
            _logger.info("Password verified successfully for user_id=%s", user.id)
            
            if user.device_token != device_token:
                _logger.info("Device token changed for user_id=%s. Old: %s, New: %s", 
                           user.id, user.device_token, device_token)
                user.sudo().write({'device_token': device_token})
                _logger.info("Device token updated for user_id=%s", user.id)
            else:
                _logger.info("Device token unchanged for user_id=%s", user.id)

            token = secrets.token_hex(32)
            access_token_dict = {
                'user_id': user.id,
                'api_key': token,
                'expiry_date': datetime.now() + timedelta(days=7)
            }
            create_access_token = request.env['partner.api.key'].sudo().create(access_token_dict)
            partner = user.partner_id

            # If no exception, login is successful
            return Response(json.dumps({
                'success': True,
                'message': 'Login Successful!',
                'user_id': user.id,
                'name': user.name,
                'email': user.login,
                # 'role': employee.job_id.name,
                # 'employee': employee_data,
                'access_token': create_access_token.api_key,

                'customer': {
                'partner_id': partner.id,
                'name': partner.name,
                'mobile': partner.mobile,
                'email': partner.email,
                'street': partner.street,
                'street2': partner.street2,
                'city': partner.city,
                'zip': partner.zip,
                'state': partner.state_id.name if partner.state_id else None,
                'country': partner.country_id.name if partner.country_id else None,}
            }), content_type='application/json')

        except Exception as e:
            # Wrong password or unexpected error
            _logger.warning("Login failed for user %s: %s", email, e)
            return Response(json.dumps({
                'success': False,
                'message': 'Invalid password!',
            }), content_type='application/json')

    @http.route('/refresh_token', type='http', auth='public',methods=['POST'], csrf=False, cors='*')
    def refresh_token(self, **kwargs):

        auth_header = request.httprequest.headers.get('Authorization')

        if not auth_header or not auth_header.startswith('Bearer '):
            return Response(
                json.dumps({
                    "success": False,
                    "message": "Bearer token required"
                }),
                content_type='application/json',
                status=400
            )

        token = auth_header.split(' ')[1].strip()

        api_key = request.env['partner.api.key'].sudo().search([
            ('api_key', '=', token)
        ], limit=1)

        if not api_key:
            return Response(
                json.dumps({
                    "success": False,
                    "message": "Invalid token"
                }),
                content_type='application/json',
                status=200
            )

        # Expiry update to next 7 days
        new_expiry = datetime.now() + timedelta(days=7)

        api_key.sudo().write({
            'expiry_date': new_expiry
        })

        return Response(
            json.dumps({
                "success": True,
                "message": "Token expiry extended successfully",
                "user_id": api_key.user_id.id,
                "user_name": api_key.user_id.name,
                "new_expiry_date": new_expiry.strftime("%Y-%m-%d %H:%M:%S")
            }),
            content_type='application/json',
            status=200
        )