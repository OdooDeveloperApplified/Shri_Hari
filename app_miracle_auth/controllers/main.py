from odoo import http
from odoo.http import request
import json
import logging
_logger = logging.getLogger(__name__)

# Import existing controllers to route the requests
try:
    from odoo.addons.app_miracle_account.controllers.main import MiracleAccountWebhookController
except ImportError:
    MiracleAccountWebhookController = None

try:
    from odoo.addons.app_miracle_product.controllers.main import MiracleProductWebhookController
except ImportError:
    MiracleProductWebhookController = None

try:
    from odoo.addons.app_miracle_voucher.controllers.main import MiracleWebhookController as MiracleVoucherWebhookController
except ImportError:
    MiracleVoucherWebhookController = None


class MiracleMasterWebhookController(http.Controller):

    @http.route('/miracle/webhook', auth='public', csrf=False, type='http', methods=['POST'])
    def miracle_master_webhook(self, **kwargs):
        try:
            raw_data = request.httprequest.data.decode('utf8', errors='ignore')
            payload = json.loads(raw_data or '{}')
            event_type = payload.get('EventType')

            _logger.info("=" * 80)
            _logger.info("Master Webhook Received | EventType: %s", event_type)

            if not event_type:
                response = request.make_response(
                    json.dumps({
                        "success": False,
                        "message": "EventType not found in payload"
                    }),
                    headers=[('Content-Type', 'application/json')]
                )
                self._log_webhook_response(payload, raw_data, response, event_type)
                return response

            # Account events: "AA" (Account Add), "AE" (Account Edit), "AD" (Account Delete)
            if event_type in ['AA', 'AE', 'AD']:
                if MiracleAccountWebhookController:
                    response = MiracleAccountWebhookController().miracle_account_webhook(**kwargs)
                    self._log_webhook_response(payload, raw_data, response, event_type)
                    return response
                else:
                    return self._module_not_installed("app_miracle_account")

            # Product events: "PA" (Product Add), "PE" (Product Edit), "PD" (Product Delete)
            elif event_type in ['PA', 'PE', 'PD']:
                if MiracleProductWebhookController:
                    response = MiracleProductWebhookController().miracle_product_webhook(**kwargs)
                    self._log_webhook_response(payload, raw_data, response, event_type)
                    return response
                else:
                    return self._module_not_installed("app_miracle_product")

            # Purchase Transaction events: "TA" (Transaction Add), "TE" (Transaction Edit), "TD" (Transaction Delete)
            elif event_type in ['TA', 'TE', 'TD']:
                if MiracleVoucherWebhookController:
                    response = MiracleVoucherWebhookController().miracle_webhook(**kwargs)
                    self._log_webhook_response(payload, raw_data, response, event_type)
                    return response
                else:
                    return self._module_not_installed("app_miracle_voucher")



            else:
                _logger.warning("Unknown EventType received: %s", event_type)
                response = request.make_response(
                    json.dumps({
                        "success": False,
                        "message": f"Unknown EventType: {event_type}"
                    }),
                    headers=[('Content-Type', 'application/json')]
                )
                self._log_webhook_response(payload, raw_data, response, event_type)
                return response

        except Exception as e:
            _logger.exception("Master Webhook routing error")
            response = request.make_response(
                json.dumps({
                    "success": False,
                    "message": f"Master Webhook routing error: {str(e)}"
                }),
                headers=[('Content-Type', 'application/json')]
            )
            # Try to log the error response
            try:
                raw_data = request.httprequest.data.decode('utf8', errors='ignore')
                payload = json.loads(raw_data or '{}')
                event_type = payload.get('EventType', '')
                self._log_webhook_response(payload, raw_data, response, event_type)
            except Exception:
                pass
            return response

    def _module_not_installed(self, module_name):
        _logger.error("%s module is not installed or available", module_name)
        return request.make_response(
            json.dumps({
                "success": False,
                "message": f"{module_name} is not installed"
            }),
            headers=[('Content-Type', 'application/json')]
        )

    def _log_webhook_response(self, payload, raw_data, response, event_type):
        try:
            client_id = payload.get('ClientId')
            api_key = payload.get('APIKey')
            company = request.env['res.company'].sudo().search([
                ('miracle_clientid', '=', client_id),
                ('miracle_apikey', '=', api_key)
            ], limit=1)
            
            if not company:
                company = request.env.company

            # Find latest session for this company to satisfy the required constraint
            session = request.env['miracle.token.session'].sudo().search([
                ('company_id', '=', company.id)
            ], order='id desc', limit=1)

            if not session:
                _logger.warning("Could not log webhook: No session found for company %s", company.name)
                return

            response_data = {}
            if response and hasattr(response, 'data'):
                try:
                    response_data = json.loads(response.data.decode('utf-8'))
                except Exception:
                    response_data = {"raw_data": response.data.decode('utf-8')}

            is_success = response_data.get('success', False)
            
            endpoint_name = f"Webhook"
            if event_type:
                endpoint_name += f" ({event_type})"
                
            request.env['miracle.api.log'].sudo().create({
                'company_id': company.id,
                'session_id': session.id,
                'name': endpoint_name,
                'request_url': request.httprequest.url,
                'request_method': request.httprequest.method.lower() if request.httprequest.method else False,
                'request_payload': raw_data,
                'response_payload': json.dumps(response_data),
                'response_code': response.status_code if hasattr(response, 'status_code') else 200,
                'status': 'success' if is_success else 'failed',
                'direction': 'inbound',
                'trigger_label': f"Incoming Webhook: {event_type}",
                'reference': payload.get('UniqueId') if payload and isinstance(payload, dict) else None,
                'res_model': getattr(response, 'res_model', None) if response else None,
                'res_id': getattr(response, 'res_id', None) if response else None,
            })
        except Exception as e:
            _logger.exception("Failed to log webhook in router")
