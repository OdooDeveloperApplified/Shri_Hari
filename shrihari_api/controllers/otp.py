from odoo import http
from odoo.http import request, Response
import json
import logging
from .token import find_user_by_identifier, normalize_whatsapp_number, complete_login

_logger = logging.getLogger(__name__)

# Placeholders pending a real decision - see docs/whatsapp_otp_login.md
# "Open decisions". Easy to tune here, nothing else needs to change.
OTP_LENGTH = 4
OTP_EXPIRY_MINUTES = 10
OTP_RESEND_COOLDOWN_SECONDS = 60
OTP_MAX_ATTEMPTS = 5


class WhatsappOtpController(http.Controller):

    @http.route('/request_otp', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def request_otp(self, **kwargs):
        mobile = kwargs.get('mobile')

        if not mobile:
            return Response(json.dumps({
                "success": False,
                "message": "mobile is required"
            }), content_type='application/json')

        user, inactive_user = find_user_by_identifier(mobile)

        if not user:
            if inactive_user:
                return Response(json.dumps({
                    "success": False,
                    "message": "Account deactivated, please contact support!"
                }), content_type='application/json')
            return Response(json.dumps({
                "success": False,
                "message": "This mobile number is not registered."
            }), content_type='application/json')

        # Always derive the number we actually send to from the matched
        # user's own stored mobile, not the raw app input - keeps the send
        # and the later verify() lookup on the same canonical value
        # regardless of what format the app happened to submit.
        wa_number = normalize_whatsapp_number(user.mobile or mobile)

        Otp = request.env['whatsapp.otp'].sudo()
        company = user.company_id

        # Store review bypass (Google Play / Apple App Store): reviewers
        # log in with this exact number and get this fixed code, with no
        # real WhatsApp message ever sent - reviewers have no way to
        # receive one. Also skips the resend cooldown, since a reviewer
        # retrying the same fixed code shouldn't get blocked by it.
        test_mobile = normalize_whatsapp_number(company.whatsapp_otp_test_mobile or '')
        is_test_login = bool(test_mobile) and wa_number == test_mobile and company.whatsapp_otp_test_code

        if not is_test_login:
            if Otp.has_recent_request(wa_number, OTP_RESEND_COOLDOWN_SECONDS):
                return Response(json.dumps({
                    "success": False,
                    "message": "Please wait before requesting another code."
                }), content_type='application/json')

            otp_record = Otp.generate_for_mobile(wa_number, length=OTP_LENGTH, expiry_minutes=OTP_EXPIRY_MINUTES)

            try:
                company._send_whatsapp_otp(wa_number, otp_record.otp)
            except Exception as e:
                _logger.error("Failed to send WhatsApp OTP to %s: %s", wa_number, e)
                # Never actually delivered - don't leave a valid, usable code
                # sitting in the database as if it were.
                otp_record.unlink()
                return Response(json.dumps({
                    "success": False,
                    "message": "Could not send OTP right now. Please try again."
                }), content_type='application/json')
        else:
            Otp.generate_for_mobile(
                wa_number,
                length=OTP_LENGTH,
                expiry_minutes=OTP_EXPIRY_MINUTES,
                code=company.whatsapp_otp_test_code,
            )

        return Response(json.dumps({
            "success": True,
            "message": "OTP sent"
        }), content_type='application/json')

    @http.route('/verify_otp', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def verify_otp(self, **kwargs):
        mobile = kwargs.get('mobile')
        code = kwargs.get('otp')
        device_token = kwargs.get('device_token')

        if not mobile or not code:
            return Response(json.dumps({
                "success": False,
                "message": "mobile and otp are required"
            }), content_type='application/json')

        user, inactive_user = find_user_by_identifier(mobile)

        if not user:
            return Response(json.dumps({
                "success": False,
                "message": "Account deactivated, please contact support!" if inactive_user else "Account not found!"
            }), content_type='application/json')

        wa_number = normalize_whatsapp_number(user.mobile or mobile)

        ok, message = request.env['whatsapp.otp'].sudo().verify(wa_number, code, max_attempts=OTP_MAX_ATTEMPTS)

        if not ok:
            return Response(json.dumps({
                "success": False,
                "message": message
            }), content_type='application/json')

        result = complete_login(user, device_token=device_token)
        return Response(json.dumps(result), content_type='application/json')
