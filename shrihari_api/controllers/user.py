from odoo.http import request, Response
from odoo import http
import json
from datetime import datetime , timedelta
from .token import validate_api_request, fmt_num, find_user_by_identifier, complete_login
import logging
_logger = logging.getLogger(__name__)


class UserController(http.Controller):
    
    @http.route('/user_login', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def user_login(self, **kwargs):
        email = kwargs.get('email')
        mobile = kwargs.get('mobile')
        password = kwargs.get('password')
        device_token = kwargs.get('device_token')
        
        login_identifier = email if email else mobile

        _logger.info("Login attempt with identifier: %s", login_identifier)

        if not login_identifier or not password:
            return Response(json.dumps({
                'success': False,
                'message': 'Email or Mobile, and password are required!',
            }), content_type='application/json')

        user, inactive_user = find_user_by_identifier(login_identifier)

        _logger.info("this is user %s", user)
        if not user:
            if inactive_user:
                _logger.warning("User found but account is deactivated: %s", login_identifier)
                return Response(json.dumps({
                    'success': False,
                    'message': 'Account deactivated, please contact support!',
                }), content_type='application/json')
            else:
                return Response(json.dumps({
                    'success': False,
                    'message': 'Account not found!',
                }), content_type='application/json')

        try:
            # Check password inside try block
            user_env = request.env(user=user)
            credential = {'login': login_identifier, 'password': password, 'type': 'password'}
            uid=user_env.user._check_credentials(credential, user_env)
            _logger.info("Password verified successfully for user_id=%s", user.id)

            result = complete_login(user, device_token=device_token)
            return Response(json.dumps(result), content_type='application/json')

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
        new_expiry = datetime.now() + timedelta(days=30)

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

    @http.route('/delete_account/<int:user_id>', type='http', auth='public', methods=['GET'], csrf=False)
    def deactive_user_account(self, user_id, **kwargs):
        try:
            if user_id:
                user = request.env['res.users'].sudo().search([('id', '=', user_id)], limit=1)
                if user:
                    # Do NOT archive User ID 7
                    if user.id == 7:
                        data = {
                            'success': True,
                            'message': 'User deactivated successfully!',
                            'user_id': user.id,
                            'login': user.login
                        }

                    else:
                        # Archive all other users
                        user.write({'active': False})

                        _logger.info(f"[API] Archived user ID {user.id}")

                        data = {
                            'success': True,
                            'message': 'User deactivated successfully!',
                            'user_id': user.id,
                            'login': user.login
                        }
                else:
                    data = {
                        'success': False,
                        'message': 'User not found!',
                    }
            else:
                data = {
                    'success': False,
                    'message': 'Missing user_id!',
                }
        except Exception as e:
            _logger.exception("Error during user deactivation")
            data = {
                'success': False,
                'message': f'Exception: {str(e)}'
            }

        return http.Response(json.dumps(data), content_type='application/json')

    @http.route('/get_app_version', type='http', auth='public', cors='*', methods=['GET'], csrf=False)
    def get_app_version(self, **kwargs):
        try:
            record = request.env['app.version'].sudo().search([], limit=1)

            if not record:
                return Response(
                    json.dumps({
                        'success': False,
                        'message': 'No app version record found'
                    }),
                    content_type='application/json'
                )

            return Response(
                json.dumps({
                    'success': True,
                    'data': {
                        'id': record.id,
                        'android_version': record.android_version,
                        'ios_version': record.ios_version
                    }
                }),
                content_type='application/json'
            )

        except Exception as e:
            return Response(
                json.dumps({
                    'success': False,
                    'message': str(e)
                }),
                content_type='application/json'
            )