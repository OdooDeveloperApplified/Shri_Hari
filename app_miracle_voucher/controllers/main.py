from odoo import http
from odoo.http import request
import json
import logging
_logger = logging.getLogger(__name__)

class MiracleWebhookController(http.Controller):

    # Changed route to prevent conflict with the master webhook in app_miracle_auth
    @http.route(['/miracle/webhook/voucher_internal'], auth='public', csrf=False, type='http', methods=['POST'])
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
            event_type = payload.get('EventType')
            if event_type == 'TD':
                _logger.info("Miracle Webhook received TD (Transaction Delete) for UniqueId: %s", unique_id)
                
                picking = request.env['stock.picking'].sudo().search([('miracle_voucher_id', '=', unique_id)], limit=1)
                
                # Check if this UniqueId belongs to a Sales Challan (HS), which maps to an outgoing picking in Odoo
                sale_order = request.env['sale.order'].sudo()
                if picking and picking.picking_type_id.code == 'outgoing' and hasattr(picking, 'sale_id') and picking.sale_id:
                    sale_order = picking.sale_id

                if sale_order:
                    _logger.info("Deleting Sale Order %s due to Miracle webhook TD event.", sale_order.name)
                    try:
                        for invoice in sale_order.invoice_ids:
                            if invoice.state != 'cancel':
                                invoice.button_cancel()
                                invoice.with_context(force_delete=True).unlink()

                        for pick in sale_order.picking_ids:
                            request.env.cr.execute("DELETE FROM stock_move_line WHERE picking_id = %s", (pick.id,))
                            request.env.cr.execute("DELETE FROM stock_move WHERE picking_id = %s", (pick.id,))
                            request.env.cr.execute("DELETE FROM stock_picking WHERE id = %s", (pick.id,))
                            
                        request.env.cr.execute("DELETE FROM sale_order_line WHERE order_id = %s", (sale_order.id,))
                        request.env.cr.execute("DELETE FROM sale_order WHERE id = %s", (sale_order.id,))
                        _logger.info("Successfully deleted Sale Order %s.", sale_order.name)
                    except Exception as e:
                        request.env.cr.rollback()
                        _logger.error("Failed to forcefully delete Sale Order: %s", str(e))
                else:
                    _logger.info("Ignoring TD webhook for %s as it is not a Sale Order / Sales Challan.", unique_id)
                            
                return request.make_response(json.dumps({"success": True, "message": "Transaction Deleted"}), headers=[('Content-Type','application/json')])

            # Normal Add/Edit flow
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

            if voucher_type == "PP":
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
                    sync_res = purchase.action_sync_purchase_from_miracle()
                    if isinstance(sync_res, dict) and (sync_res.get('type') == 'ir.actions.client' or sync_res.get('IsError')):
                        # Odoo notifications usually have 'params': {'type': 'danger'}
                        is_danger = sync_res.get('params', {}).get('type') == 'danger' or sync_res.get('IsError')
                        if is_danger:
                            _logger.error("Purchase Sync Error: %s", sync_res)
                            return request.make_response(json.dumps({"success": False, "message": str(sync_res)}), headers=[("Content-Type", "application/json")])

                    # Properly confirm it so Inventory Receipts are generated
                    if purchase.state in ['draft', 'sent'] and purchase.order_line:
                        purchase.with_context(skip_miracle_sync=True).button_confirm()
                        
                    # Automatically validate the receipt to update inventory instantly
                    for picking in purchase.picking_ids:
                        if picking.state not in ['cancel', 'done']:
                            picking.sudo().with_context(skip_miracle_sync=True).write({
                                'is_miracle_voucher': True,
                                'miracle_voucher_id': unique_id
                            })
                            for move in picking.move_ids:
                                move.quantity = move.product_uom_qty
                            picking.with_context(skip_miracle_sync=True).button_validate()

            elif voucher_type == "HS":
                sale = request.env['sale.order'].sudo().with_company(company).search([
                    ('miracle_sale_order_id', '=', unique_id)
                ])

                if not sale:
                    partner = request.env['res.partner'].sudo().with_company(company).search([
                        ('miracle_account_id', '=', data.get('acc'))
                    ], limit=1)

                    if not partner:
                        _logger.error("Customer not found for account %s", data.get('acc'))
                    else:
                        sale = request.env['sale.order'].sudo().with_company(company).create({
                            'partner_id': partner.id,
                            'miracle_sale_order_id': unique_id
                        })

                if sale:
                    # Sync the order lines directly
                    sync_res = sale.action_sync_sale_from_miracle()
                    if isinstance(sync_res, dict) and (sync_res.get('type') == 'ir.actions.client' or sync_res.get('IsError')):
                        is_danger = sync_res.get('params', {}).get('type') == 'danger' or sync_res.get('IsError')
                        if is_danger:
                            _logger.error("Sale Sync Error: %s", sync_res)
                            return request.make_response(json.dumps({"success": False, "message": str(sync_res)}), headers=[("Content-Type", "application/json")])
                            
                    # Properly confirm it so Inventory Deliveries are generated
                    if sale.state in ['draft', 'sent'] and sale.order_line:
                        sale.with_context(skip_miracle_sync=True).action_confirm()
                        
                    # Automatically validate the delivery to update inventory instantly
                    for picking in sale.picking_ids:
                        if picking.state not in ['cancel', 'done']:
                            picking.sudo().with_context(skip_miracle_sync=True).write({
                                'is_miracle_voucher': True,
                                'miracle_voucher_id': unique_id
                            })
                            for move in picking.move_ids:
                                move.quantity = move.product_uom_qty
                            picking.with_context(skip_miracle_sync=True).button_validate()

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