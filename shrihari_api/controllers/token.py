from odoo.http import  Response, request
import json
from datetime import datetime
import pytz
import logging

_logger = logging.getLogger(__name__)

def fmt_num(value):
    """Format a numeric API value: 2 decimal places when it's a whole
    number, 4 decimal places when it actually carries a fractional part.
    None passes through unchanged so optional fields still serialize as
    JSON null rather than the string "None"."""
    if value is None:
        return None
    value = float(value)
    if value == int(value):
        return f"{value:.2f}"
    return f"{value:.4f}"

def to_local_str(user, dt_value, fmt='%Y-%m-%d %H:%M:%S'):
    """Convert a naive-UTC Odoo Datetime value to the authenticated user's
    local time, the same way the Odoo web client does for a logged-in user.

    Timezone is resolved dynamically, never hardcoded:
      1. the API caller's own Preferences > Timezone (res.users.tz)
      2. their company's timezone, if the user hasn't set one
      3. UTC, as a last-resort default
    """
    if not dt_value:
        return None

    tz_name = user.tz or user.company_id.partner_id.tz or 'UTC'
    try:
        local_tz = pytz.timezone(tz_name)
    except Exception:
        _logger.warning("Unknown timezone '%s' for user %s, falling back to UTC", tz_name, user.id)
        local_tz = pytz.utc

    return pytz.utc.localize(dt_value).astimezone(local_tz).strftime(fmt)

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

def resolve_miracle_account(request, kwargs):
    """Common gate for Miracle proxy endpoints (AccountBalance, GetAccount,
    and future ones): authenticate the caller the normal way, then take the
    Miracle account id straight from what the app sent.

    ACCEPTED RISK - by explicit decision, not an oversight: miracle_account_id
    is trusted as-is here and is NOT cross-checked against the authenticated
    user's own linked account (user.partner_id.miracle_account_id). A caller
    with a valid token could in principle supply a different account's id.
    If that ever needs closing, this is the one place to add the check -
    every proxy endpoint resolves the account through this function, so the
    fix only has to happen once, here.

    Returns (user, company, miracle_account_id, error_response).

    Error shape: if the auth check itself fails (bad/missing token), the
    error uses this API's own {success, message} shape, same as every
    other endpoint. Past that point - missing miracle_account_id - the
    error switches to Miracle's own {IsError, ErrorCode, Message} shape,
    since everything from here on is meant to look like Miracle itself
    answered, not shrihari_api.
    """
    user, error_response = validate_api_request(request, kwargs)
    if error_response:
        return None, None, None, error_response

    company = user.company_id or request.env.company
    miracle_account_id = kwargs.get('miracle_account_id')

    if not miracle_account_id:
        return None, None, None, Response(json.dumps({
            "IsError": True,
            "ErrorCode": "NOMIRACLEACC",
            "Message": "miracle_account_id is required."
        }), content_type='application/json')

    return user, company, miracle_account_id, None

def call_miracle_relay(company, endpoint, method, payload):
    """Call Miracle through the shared miracle_api_call() and hand back its
    response as-is - success or error - whenever Miracle actually answered.
    We never build our own error body out of a response Miracle sent; the
    only time this originates its own message is when Miracle never
    answered at all (network failure, timeout, DNS), since there is
    nothing of Miracle's left to relay in that case.
    """
    try:
        data = company.miracle_api_call(endpoint, method, payload)
        return Response(json.dumps(data), content_type='application/json')
    except Exception as e:
        resp = getattr(e, 'response', None)
        if resp is not None:
            # Miracle did answer, just with a non-2xx status - relay its
            # exact body and status code untouched.
            return Response(resp.text, status=resp.status_code, content_type='application/json')
        _logger.warning("Miracle call to %s got no response at all: %s", endpoint, e)
        return Response(json.dumps({
            "IsError": True,
            "ErrorCode": "MIRACLEUNAVAILABLE",
            "Message": "Could not reach Miracle Cloud ERP. Please try again."
        }), content_type='application/json')

