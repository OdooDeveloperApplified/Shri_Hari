from odoo import http,fields
from odoo.http import request, Response
from .token import validate_api_request, to_local_str, fmt_num, resolve_miracle_account, call_miracle_relay
from datetime import datetime
import json
import logging

_logger = logging.getLogger(__name__)

############### API to Get Miracle Credentials ########################## 
class MiracleCredentialAPI(http.Controller):

    @http.route('/get_miracle_credentials', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_miracle_credentials(self, **kwargs):

        # Validate user (requires user_id in kwargs and valid Bearer token)
        user, error_response = validate_api_request(request, kwargs)
        if error_response:
            return error_response

        company = user.company_id or request.env.company
        partner = user.partner_id

        # Hand back Odoo's own currently-active Miracle token/session, so the
        # app can reuse it instead of authenticating against Miracle on its
        # own (which invalidates whatever token Odoo is holding).
        active_token = ""
        token_generated_at = None
        token_expiry_at = None
        try:
            session = company.sudo()._get_valid_session()
            if session:
                active_token = session.token
                token_generated_at = session.generated_at
                token_expiry_at = session.expiry_at
        except Exception as e:
            _logger.warning("Could not fetch/refresh Miracle session for company %s: %s", company.id, e)

        data = [{
            "id": company.id,
            "name": company.name,
            "icon": "business",
            "MIRACLE_BASE_URL": company.miracle_base_url or "",
            "URL_KEY": company.miracle_urlkey or "",
            "CLIENT_ID": company.miracle_clientid or "",
            "API_KEY": company.miracle_apikey or "",
            "ACCID": partner.miracle_account_id or "",
            "ACTIVE_TOKEN": active_token,
            "TOKEN_GENERATED_AT": to_local_str(user,token_generated_at),
            "TOKEN_EXPIRY_AT": to_local_str(user,token_expiry_at)
        }]

        return Response(json.dumps({
            "success": True,
            "data": data
        }), content_type='application/json')

############### Miracle proxy APIs (app no longer calls Miracle directly) ##########################
class MiracleProxyAPI(http.Controller):

    @http.route('/account_balance', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_account_balance(self, **kwargs):

        user, company, miracle_account_id, error_response = resolve_miracle_account(request, kwargs)
        if error_response:
            return error_response

        return call_miracle_relay(company, company.miracle_account_balance_url, 'post', {"accid": [miracle_account_id]})

    @http.route('/get_account', type='http', auth='public', cors='*', methods=['GET'], csrf=False)
    def get_account_details(self, **kwargs):

        user, company, miracle_account_id, error_response = resolve_miracle_account(request, kwargs)
        if error_response:
            return error_response

        # Reuses the same URL field app_miracle_account already defines and
        # uses for its own account sync - not a new endpoint concept.
        return call_miracle_relay(company, company.miracle_get_account_url, 'get', {"id": miracle_account_id})

    @http.route('/account_ledger', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_account_ledger(self, **kwargs):

        user, company, miracle_account_id, error_response = resolve_miracle_account(request, kwargs)
        if error_response:
            return error_response

        fromdate = kwargs.get('fromdate')
        todate = kwargs.get('todate')

        if not fromdate or not todate:
            return Response(json.dumps({
                "IsError": True,
                "ErrorCode": "MISSINGDATE",
                "Message": "fromdate and todate are required."
            }), content_type='application/json')

        payload = {
            "fromdate": fromdate,
            "todate": todate,
            # Fixed column set - matches exactly what the app has always
            # requested for this call, so there's no need for it to be
            # parameterized from the app side.
            "rptfield": [
                "accid", "accnm", "accgrpnm", "opbal",
                "totalcr", "totaldb", "clbal", "citynm", "statenm", "gstin"
            ],
            "rptfilter": {
                "accid": [miracle_account_id]
            }
        }

        return call_miracle_relay(company, company.miracle_account_ledger_url, 'post', payload)

    @http.route('/account_voucher_list', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_account_voucher_list(self, **kwargs):

        user, company, miracle_account_id, error_response = resolve_miracle_account(request, kwargs)
        if error_response:
            return error_response

        # Note: Miracle's own field names for this call are camelCase
        # (fromDate/toDate/rptFilter), unlike AccountLedger's lowercase
        # (fromdate/todate/rptfilter) - kept exactly as Miracle documents
        # it rather than normalizing the two to match each other.
        from_date = kwargs.get('fromDate')
        to_date = kwargs.get('toDate')

        if not from_date or not to_date:
            return Response(json.dumps({
                "IsError": True,
                "ErrorCode": "MISSINGDATE",
                "Message": "fromDate and toDate are required."
            }), content_type='application/json')

        payload = {
            "fromDate": from_date,
            "toDate": to_date,
            "rptFilter": {
                "accid": [miracle_account_id]
            }
        }

        return call_miracle_relay(company, 'TPA/M2/V1/AccountVoucherList', 'post', payload)

    @http.route('/generate_file', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def generate_file(self, **kwargs):

        user, company, miracle_account_id, error_response = resolve_miracle_account(request, kwargs)
        if error_response:
            return error_response

        rpt_type = kwargs.get('rptType')

        if rpt_type == 'RPT001':
            # Account Statement PDF - keyed by the caller's own account.
            from_date = kwargs.get('fromDate')
            to_date = kwargs.get('toDate')
            if not from_date or not to_date:
                return Response(json.dumps({
                    "IsError": True,
                    "ErrorCode": "MISSINGDATE",
                    "Message": "fromDate and toDate are required for RPT001."
                }), content_type='application/json')
            payload = {
                "rptType": "RPT001",
                "uniqueId": miracle_account_id,
                "fromDate": from_date,
                "toDate": to_date,
            }

        elif rpt_type == 'RPT002':
            # Ageing / Outstanding Report PDF - also keyed by the account.
            report_date = kwargs.get('reportDate')
            if not report_date:
                return Response(json.dumps({
                    "IsError": True,
                    "ErrorCode": "MISSINGDATE",
                    "Message": "reportDate is required for RPT002."
                }), content_type='application/json')
            payload = {
                "rptType": "RPT002",
                "uniqueId": miracle_account_id,
                "reportDate": report_date,
            }

        elif rpt_type == 'RPT003':
            # Voucher / Invoice Print PDF - keyed by a VOUCHER id, not an
            # account id. Trusted as sent by the app, same accepted-risk
            # basis as miracle_account_id elsewhere in this file - see
            # resolve_miracle_account()'s docstring for the reasoning and
            # where to add a check later if this ever needs closing.
            voucher_id = kwargs.get('voucher_id') or kwargs.get('uniqueId')
            if not voucher_id:
                return Response(json.dumps({
                    "IsError": True,
                    "ErrorCode": "MISSINGVOUCHER",
                    "Message": "voucher_id is required for RPT003."
                }), content_type='application/json')
            payload = {
                "rptType": "RPT003",
                "uniqueId": voucher_id,
            }

        else:
            return Response(json.dumps({
                "IsError": True,
                "ErrorCode": "BADRPTTYPE",
                "Message": "rptType must be one of RPT001, RPT002, RPT003."
            }), content_type='application/json')

        return call_miracle_relay(company, 'TPA/M2/V1/GenerateFile', 'post', payload)


