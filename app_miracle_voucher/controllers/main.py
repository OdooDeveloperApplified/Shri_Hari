from odoo import http
from odoo.http import request
import json
import logging
_logger = logging.getLogger(__name__)

class MiracleWebhookController(http.Controller):

    @http.route('/miracle/webhook', auth='public', csrf=False, type='http', methods=['POST'])
    def miracle_webhook(self, **kwargs):
        try:
            headers = dict(request.httprequest.headers)
            raw_data = request.httprequest.data.decode('utf8',errors='ignore')

            _logger.info("=" * 80)
            # _logger.info("Miracle Webhook Received")
            # _logger.info("Headers")
            # _logger.info(json.dumps(headers,indent=1))
            # _logger.info("Body")
            _logger.info(raw_data)

            payload = json.loads(raw_data or '{}')

            unique_id = payload.get('UniqueId')

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
            ],limit=1)

            if not company:
                _logger.error(
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

            response = company._action_get_voucher_from_miracle({
                "id": unique_id
            })

            # _logger.info("Get voucher response")
            _logger.info(json.dumps(response,indent=4))

            if response.get("IsError"):
                return request.make_response(
                    json.dumps({
                        "success": False,
                        "message": response.get("Message")
                    }),
                    headers=[("Content-Type", 'application/json')]
                )
            
            data = response.get("DataModel",{})
            voucher_type = data.get("voutyp")
            # _logger.info("Voucher type %s",voucher_type)

            # if voucher_type == "QP":
            #     purchase = request.env['purchase.order'].sudo().with_company(company).search([
            #         ('miracle_purchase_quotation_id','=',unique_id)
            #     ])

            #     if not purchase:
            #         partner = request.env['res.partner'].sudo().with_company(company).search([
            #             ('miracle_account_id','=', data.get('acc'))
            #         ], limit=1)

            #         if not partner:
            #             _logger.error("Vendor not found for account %s",data.get('acc'))
            #         else:
            #             purchase = request.env['purchase.order'].sudo().with_company(company).create({
            #                 'partner_id': partner.id,
            #                 'miracle_purchase_quotation_id': unique_id
            #             })

            #     if purchase:
            #         purchase.action_sync_purchase_from_miracle()

            if voucher_type == "HP":
                purchase = request.env['purchase.order'].sudo().with_company(company).search([
                    ('miracle_purchase_order_id','=',unique_id)
                ])

                if not purchase:
                    partner = request.env['res.partner'].sudo().with_company(company).search([
                        ('miracle_account_id','=', data.get('acc'))
                    ], limit=1)

                    if not partner:
                        _logger.error("Vendor not found for account %s",data.get('acc'))
                    else:
                        purchase = request.env['purchase.order'].sudo().with_company(company).create({
                            'partner_id': partner.id,
                            'miracle_purchase_order_id': unique_id
                        })

                if purchase:
                    # Sync the order lines directly
                    purchase.action_sync_purchase_from_miracle()
                    # Properly confirm it so Inventory Receipts are generated
                    if purchase.state in ['draft', 'sent']:
                        purchase.button_confirm()
                        
                    # Automatically validate the receipt to update inventory instantly
                    for picking in purchase.picking_ids:
                        if picking.state not in ['cancel', 'done']:
                            for move in picking.move_ids:
                                move.quantity = move.product_uom_qty
                            picking.button_validate()

            else:
                _logger.info("Voucher Type %s not handled yet",voucher_type)
                
            _logger.info("=" * 80)

            return request.make_response(
                json.dumps({
                    "success": True,
                    "message": "Webhook Processed "
                }),
                headers=[("Content-Type","application/json")]
            )

        except Exception as e:
            _logger.exception('Miracle webhook error')

            return request.make_response(
                json.dumps({
                    "success": False,
                    "message": str(e)
                }),
                headers=[('Content-Type','application/json')]
            )