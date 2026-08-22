from odoo import http
from odoo.http import request
import json
import logging
_logger = logging.getLogger(__name__)

# class MiracleMasterWebhookController(http.Controller):

#     @http.route('/miracle/webhook', auth='public', csrf=False, type='http', methods=['POST'])
#     def miracle_master_webhook(self, **kwargs):
#         raw_data = ""
#         event_type = ""
#         company = None
#         try:
#             raw_data = request.httprequest.data.decode('utf8', errors='ignore')
#             payload = json.loads(raw_data or '{}')
#             event_type = payload.get('EventType')

#             _logger.info("=" * 80)
#             _logger.info("Master Webhook Received | EventType: %s", event_type)
#             _logger.info("Payload: %s", payload)

#             unique_id = payload.get('UniqueId')
#             client_id = payload.get('ClientId')
#             api_key = payload.get('APIKey')

#             if not unique_id:
#                 return self._make_error_response("UniqueId not found", company, event_type, raw_data)

#             if not event_type:
#                 return self._make_error_response("EventType not found in payload", company, event_type, raw_data)

#             company = request.env['res.company'].sudo().search([
#                 ('miracle_clientid', '=', client_id),
#                 ('miracle_apikey', '=', api_key)
#             ], limit=1)

#             if not company:
#                 _logger.error("Company not found for ClientId=%s and APIKey=%s", client_id, api_key)
#                 return self._make_error_response("Company configuration not found", company, event_type, raw_data)

#             # ---------------------------------------------------------
#             # 1. ACCOUNT LOGIC (AA, AE)
#             # ---------------------------------------------------------
#             if event_type in ['AA', 'AE']:
#                 partner = request.env['res.partner'].sudo().with_company(company).search([
#                     ('miracle_account_id', '=', unique_id),
#                     ('is_miracle_account', '=', True)
#                 ], limit=1)

#                 api_response = None
#                 if not partner:
#                     api_response = company._action_get_account_from_miracle({"id": unique_id})
#                     if not api_response or api_response.get("IsError") or not api_response.get("DataModel"):
#                         _logger.info("Ignored account webhook for %s because no details were found in Miracle.", unique_id)
#                         return self._make_success_response("Ignored: No details found in Miracle", company, event_type, raw_data)

#                     partner = request.env['res.partner'].sudo().with_company(company).create({
#                         'name': 'Pending Miracle Sync',
#                         'miracle_account_id': unique_id,
#                         'is_miracle_account': True,
#                         'miracle_source_company_id': company.id,
#                         'company_id': False,
#                     })
#                     _logger.info("Created shell partner for %s", unique_id)

#                 if partner:
#                     partner.action_sync_account_from_miracle(api_response=api_response)
#                     _logger.info("Successfully synced account %s from webhook", unique_id)
#                     partner.action_upload_account_to_miracle(from_webhook=True)
#                     _logger.info("Successfully pushed account %s to target companies", unique_id)

#                 return self._make_success_response("Account Webhook Processed", company, event_type, raw_data)

#             # ---------------------------------------------------------
#             # 2. PRODUCT LOGIC (PA, PE)
#             # ---------------------------------------------------------
#             elif event_type in ['PA', 'PE']:
#                 product = request.env['product.template'].sudo().with_company(company).search([
#                     ('miracle_product_id', '=', unique_id)
#                 ], limit=1)

#                 api_response = None
#                 if not product:
#                     api_response = company._action_get_product_from_miracle({"id": unique_id})
#                     if not api_response or api_response.get("IsError") or not api_response.get("DataModel"):
#                         _logger.info("Ignored product webhook for %s because no details were found in Miracle.", unique_id)
#                         return self._make_success_response("Ignored: No details found in Miracle", company, event_type, raw_data)

#                     product = request.env['product.template'].sudo().with_company(company).create({
#                         'name': 'Pending Miracle Sync',
#                         'miracle_product_id': unique_id,
#                         'is_miracle_product': True,
#                         'miracle_source_company_id': company.id,
#                         'company_id': False,
#                         'responsible_id': False,
#                     })
#                     _logger.info("Created shell product for %s", unique_id)

#                 if product:
#                     product.action_sync_from_miracle(api_response=api_response)
#                     _logger.info("Successfully synced product %s from webhook", unique_id)
#                     product.action_upload_to_miracle(from_webhook=True)
#                     _logger.info("Successfully pushed product %s to target companies", unique_id)

#                 return self._make_success_response("Product Webhook Processed", company, event_type, raw_data)

#             # ---------------------------------------------------------
#             # 3. PURCHASE TRANSACTION LOGIC (TA, TE)
#             # ---------------------------------------------------------
#             elif event_type in ['TA', 'TE']:
#                 response = company._action_get_voucher_from_miracle({"id": unique_id})
#                 _logger.info(json.dumps(response, indent=4))

#                 if response.get("IsError"):
#                     return self._make_error_response(response.get("Message"), company, event_type, raw_data)

#                 data = response.get("DataModel", {})
#                 voucher_type = data.get("voutyp")

#                 if voucher_type == "HP":
#                     purchase = request.env['purchase.order'].sudo().with_company(company).search([
#                         ('miracle_purchase_order_id', '=', unique_id)
#                     ], limit=1)

#                     if not purchase:
#                         partner = request.env['res.partner'].sudo().with_company(company).search([
#                             ('miracle_account_id', '=', data.get('acc'))
#                         ], limit=1)

#                         if not partner:
#                             _logger.error("Vendor not found for account %s", data.get('acc'))
#                         else:
#                             purchase = request.env['purchase.order'].sudo().with_company(company).create({
#                                 'partner_id': partner.id,
#                                 'miracle_purchase_order_id': unique_id
#                             })

#                     if purchase:
#                         purchase.action_sync_purchase_from_miracle()
#                         if purchase.state in ['draft', 'sent']:
#                             purchase.button_confirm()

#                         for picking in purchase.picking_ids:
#                             if picking.state not in ['cancel', 'done']:
#                                 for move in picking.move_ids:
#                                     move.quantity = move.product_uom_qty
#                                 picking.button_validate()

#                 else:
#                     _logger.info("Voucher Type %s not handled yet", voucher_type)

#                 return self._make_success_response("Purchase Webhook Processed", company, event_type, raw_data)

#             # ---------------------------------------------------------
#             # 4. DELETE EVENTS (IGNORED FOR NOW)
#             # ---------------------------------------------------------
#             elif event_type in ['AD', 'PD', 'TD']:
#                 _logger.info("Delete event received and intentionally ignored: %s", event_type)
#                 return self._make_success_response(f"Delete event {event_type} ignored (not yet implemented)", company, event_type, raw_data)

#             else:
#                 _logger.warning("Unknown EventType received: %s", event_type)
#                 return self._make_error_response(f"Unknown EventType: {event_type}", company, event_type, raw_data)

#         except Exception as e:
#             _logger.exception("Master Webhook execution error")
#             return self._make_error_response(f"Master Webhook execution error: {str(e)}", company, event_type, raw_data)

#     def _log_webhook(self, company, event_type, raw_data, response_data, is_success):
#         try:
#             company_id = company.id if company else request.env.company.id
#             endpoint_name = f"Webhook"
#             if event_type:
#                 endpoint_name += f" ({event_type})"
                
#             request.env['miracle.api.log'].sudo().create({
#                 'company_id': company_id,
#                 'name': endpoint_name,
#                 'request_url': request.httprequest.url,
#                 'request_method': request.httprequest.method,
#                 'request_payload': raw_data,
#                 'response_payload': json.dumps(response_data),
#                 'response_code': 200,
#                 'status': 'success' if is_success else 'failed',
#                 'session_id': False
#             })
#         except Exception as e:
#             _logger.exception("Failed to log webhook")

#     def _make_success_response(self, message, company=None, event_type="", raw_data=""):
#         response_data = {"success": True, "message": message}
#         self._log_webhook(company, event_type, raw_data, response_data, True)
#         return request.make_response(
#             json.dumps(response_data),
#             headers=[('Content-Type', 'application/json')]
#         )

#     def _make_error_response(self, message, company=None, event_type="", raw_data=""):
#         response_data = {"success": False, "message": message}
#         self._log_webhook(company, event_type, raw_data, response_data, False)
#         return request.make_response(
#             json.dumps(response_data),
#             headers=[('Content-Type', 'application/json')]
#         )


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

            # Account events: "AA" (Account Add), "AE" (Account Edit)
            if event_type in ['AA', 'AE']:
                if MiracleAccountWebhookController:
                    response = MiracleAccountWebhookController().miracle_account_webhook(**kwargs)
                    self._log_webhook_response(payload, raw_data, response, event_type)
                    return response
                else:
                    return self._module_not_installed("app_miracle_account")

            # Product events: "PA" (Product Add), "PE" (Product Edit)
            elif event_type in ['PA', 'PE']:
                if MiracleProductWebhookController:
                    response = MiracleProductWebhookController().miracle_product_webhook(**kwargs)
                    self._log_webhook_response(payload, raw_data, response, event_type)
                    return response
                else:
                    return self._module_not_installed("app_miracle_product")

            # Purchase Transaction events: "TA" (Transaction Add), "TE" (Transaction Edit)
            elif event_type in ['TA', 'TE']:
                if MiracleVoucherWebhookController:
                    response = MiracleVoucherWebhookController().miracle_webhook(**kwargs)
                    self._log_webhook_response(payload, raw_data, response, event_type)
                    return response
                else:
                    return self._module_not_installed("app_miracle_voucher")

            # Delete events: "AD" (Account), "PD" (Product), "TD" (Transaction)
            elif event_type in ['AD', 'PD', 'TD']:
                _logger.info("Delete event received and intentionally ignored: %s", event_type)
                response = request.make_response(
                    json.dumps({
                        "success": True,
                        "message": f"Delete event {event_type} ignored (not yet implemented)"
                    }),
                    headers=[('Content-Type', 'application/json')]
                )
                self._log_webhook_response(payload, raw_data, response, event_type)
                return response

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
            })
        except Exception as e:
            _logger.exception("Failed to log webhook in router")
