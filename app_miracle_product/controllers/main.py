from odoo import http
from odoo.http import request
import json
import logging

_logger = logging.getLogger(__name__)

class MiracleProductWebhookController(http.Controller):

    @http.route('/miracle/webhook/product', auth='public', csrf=False, type='http', methods=['POST'])
    def miracle_product_webhook(self, **kwargs):
        try:
            _logger.info("=" * 80)
            # _logger.info("Miracle Product Webhook Received")

            raw_data = request.httprequest.data.decode('utf8', errors='ignore')
            # _logger.info(raw_data)

            payload = json.loads(raw_data or '{}')
            # _logger.info("Payload: %s", payload)

            unique_id = payload.get('UniqueId')
            # _logger.info("UniqueId: %s", unique_id)

            if not unique_id:
                return request.make_response(
                    json.dumps({
                        "success": False,
                        "message": "UniqueId not found"
                    }),
                    headers=[('Content-Type','application/json')]
                )

            client_id = payload.get('ClientId')
            api_key = payload.get('APIKey')

            company = request.env['res.company'].sudo().search([
                ('miracle_clientid', '=', client_id),
                ('miracle_apikey', '=', api_key)
            ], limit=1)

            if not company:
                _logger.info(
                    "Company not found for ClientId=%s and APIKey=%s",
                    client_id,
                    api_key
                )
                return request.make_response(
                    json.dumps({
                        "success": False,
                        "message": "Company configuration not found"
                    }),
                    headers=[('Content-Type', 'application/json')]
                )

            # Check if Product exists
            product = request.env['product.template'].sudo().with_company(company).search([
                ('miracle_product_id', '=', unique_id)
            ], limit=1)

            api_response = None

            if not product:
                # Ask Miracle for details FIRST before creating shell
                api_response = company._action_get_product_from_miracle({"id": unique_id})
                
                if not api_response or api_response.get("IsError") or not api_response.get("DataModel"):
                    _logger.info("Ignored product webhook for %s because no details were found in Miracle.", unique_id)
                    return request.make_response(
                        json.dumps({
                            "success": True,
                            "message": "Ignored: No details found in Miracle"
                        }),
                        headers=[("Content-Type","application/json")]
                    )

                # Valid details exist! Safely create shell.
                product = request.env['product.template'].sudo().with_company(company).create({
                    'name': 'Pending Miracle Sync',
                    'miracle_product_id': unique_id,
                    'is_miracle_product': True,
                    'miracle_source_company_id': company.id,
                    'company_id': False,
                    'responsible_id': False,
                })
                # _logger.info("Created shell product for %s", unique_id)

            # Trigger Sync (Action uses the fetched details or pulls them again)
            if product:
                # 1. Download full product details from Source Company
                product.action_sync_from_miracle(api_response=api_response)
                _logger.info("Successfully synced product %s from webhook", unique_id)

                # 2. Automatically push it to Target Companies
                product.action_upload_to_miracle(from_webhook=True)
                _logger.info("Successfully pushed product %s to target companies", unique_id)

            # _logger.info("=" * 80)

            return request.make_response(
                json.dumps({
                    "success": True,
                    "message": "Product Webhook Processed"
                }),
                headers=[("Content-Type","application/json")]
            )

        except Exception as e:
            _logger.exception('Miracle product webhook error')
            return request.make_response(
                json.dumps({
                    "success": False,
                    "message": str(e)
                }),
                headers=[('Content-Type','application/json')]
            )
