from odoo.http import request, Response
from odoo import http
import json
from datetime import datetime , timedelta
import secrets
from .token import validate_api_request, fmt_num
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

        # Smart phone matching logic:
        # If the input contains at least 10 digits, we extract the last 10 digits
        digits_only = ''.join(filter(str.isdigit, login_identifier))
        if len(digits_only) >= 10:
            phone_pattern = '%' + '%'.join(list(digits_only[-10:])) + '%'
            search_domain = ['|', ('login', '=', login_identifier), ('mobile', '=like', phone_pattern)]
        else:
            search_domain = ['|', ('login', '=', login_identifier), ('mobile', '=', login_identifier)]

        #  Search for the user using the smart domain
        candidates = request.env['res.users'].sudo().search(search_domain)
        
        user = request.env['res.users'].sudo()
        inactive_user = request.env['res.users'].sudo()
        
        # Strict Python filter
        for candidate in candidates:
            match = False
            if len(digits_only) >= 10:
                last_10 = digits_only[-10:]
                c_login_digits = ''.join(filter(str.isdigit, candidate.login or ""))
                c_mobile_digits = ''.join(filter(str.isdigit, candidate.mobile or ""))
                
                if (len(c_login_digits) >= 10 and c_login_digits[-10:] == last_10) or \
                   (len(c_mobile_digits) >= 10 and c_mobile_digits[-10:] == last_10):
                    match = True
            else:
                match = (candidate.login == login_identifier or candidate.mobile == login_identifier)
                
            if match:
                if candidate.active:
                    user = candidate
                    break
                elif not inactive_user:
                    inactive_user = candidate
        
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
            
            if user.device_token != device_token:
                _logger.info("Device token changed for user_id=%s. Old: %s, New: %s", 
                           user.id, user.device_token, device_token)
                user.sudo().write({'device_token': device_token})
                _logger.info("Device token updated for user_id=%s", user.id)
            else:
                _logger.info("Device token unchanged for user_id=%s", user.id)

            # Search for an existing active token
            existing_token = request.env['partner.api.key'].sudo().search([
                ('user_id', '=', user.id),
                ('expiry_date', '>', datetime.now())
            ], limit=1, order='expiry_date desc')

            if existing_token:
                # Reuse the existing token
                token = existing_token.api_key
            else:
                # Create a new token
                token = secrets.token_hex(32)
                access_token_dict = {
                    'user_id': user.id,
                    'api_key': token,
                    'expiry_date': datetime.now() + timedelta(days=7)
                }
                request.env['partner.api.key'].sudo().create(access_token_dict)

            # Stock sync has been moved to products_by_category for live updates

            partner = user.partner_id.with_company(user.company_id)

            # If no exception, login is successful
            return Response(json.dumps({
                'success': True,
                'message': 'Login Successful!',
                'user_id': user.id,
                'name': user.name,
                'email': user.login,
                'access_token': token,
                'customer': {
                    'partner_id': partner.id,
                    'name': partner.name,
                    'miracle_account_id': partner.miracle_account_id,
                    'mobile': partner.mobile,
                    'email': partner.email,
                    'street': partner.street,
                    'street2': partner.street2,
                    'city': partner.city,
                    'zip': partner.zip,
                    'state': partner.state_id.name if partner.state_id else None,
                    'country': partner.country_id.name if partner.country_id else None,
                    'credit_limit': fmt_num(partner.credit_limit),
                    'crdays': int(''.join(filter(str.isdigit, partner.property_payment_term_id.name or "0")) or 0)
                }
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