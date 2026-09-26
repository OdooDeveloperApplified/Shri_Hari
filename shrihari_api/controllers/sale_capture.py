from odoo import http,fields
from odoo.http import request, Response
from .token import validate_api_request, to_local_str, fmt_num, resolve_miracle_account, call_miracle_relay
from datetime import datetime
import json
import logging

_logger = logging.getLogger(__name__)


def _get_applied_slab(order, line):
    """Which pricing slab (product.pricelist.item) actually priced this line,
    using Odoo's own rule-selection (_get_product_price_rule) so it can never
    disagree with what the order was really charged."""
    if not order.pricelist_id or not line.product_id:
        return None

    _price, rule_id = order.pricelist_id._get_product_price_rule(
        line.product_id, line.product_uom_qty, uom=line.product_uom,
        date=order.date_order or fields.Date.context_today(order)
    )
    if not rule_id:
        return None

    item = request.env['product.pricelist.item'].sudo().browse(rule_id)
    return {
        "slab_id": item.id,
        "min_qty": fmt_num(item.min_quantity),
        "discount_type": item.compute_price,  # 'fixed' or 'percentage'
        "discount_percent": fmt_num(item.percent_price) if item.compute_price == 'percentage' else None,
    }


class SaleCaptureCreateAPI(http.Controller):

    @http.route('/create_sale_capture', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def create_sale_capture(self, **kwargs):

        # Validate User
        user, error_response = validate_api_request(request, kwargs)
        if error_response:
            return error_response
    
        partner = user.partner_id

        if not partner:
            return Response(json.dumps({
                "success": False,
                "message": "Logged-in user has no associated contact"
            }), content_type='application/json')

        # Create environment bound to the authenticated user so context (allowed_company_ids) is correct
        user_env = request.env(user=user)

        sale_order_vals = {
            'partner_id': partner.id,
            'user_id': user.id,
            'order_line': []
        }
        if user.company_id.mobile_app_pricelist_id:
            sale_order_vals['pricelist_id'] = user.company_id.mobile_app_pricelist_id.id

        # --- 1. GET LIVE STOCK FROM MIRACLE FIRST ---
        # Fetch fresh stock from Miracle before processing the order
        miracle_ids = []
        all_product_ids = []
        temp_idx = 0
        while True:
            pid = kwargs.get(f'line_product_id[{temp_idx}]')
            if not pid:
                break
            prod = user_env['product.product'].sudo().browse(int(pid))
            if prod.exists():
                all_product_ids.append(prod.id)
                if prod.miracle_product_id:
                    miracle_ids.append(prod.miracle_product_id)
            temp_idx += 1
        
        if all_product_ids:
            try:
                # 1. Lock all products at once in a consistent order to prevent deadlocks
                sorted_pids = tuple(sorted(list(set(all_product_ids))))
                user_env.cr.execute("SELECT id FROM product_product WHERE id IN %s ORDER BY id FOR UPDATE", (sorted_pids,))
                
                # 2. Fetch fresh stock from Miracle ONLY AFTER acquiring the lock!
                # This guarantees we don't overwrite Odoo's stock with outdated Miracle data.
                if miracle_ids:
                    user.company_id._action_get_miracle_stock_ledger(miracle_product_ids=miracle_ids)
                    
            except Exception as e:
                _logger.error("Concurrency or Miracle Sync Exception during checkout: %s", str(e), exc_info=True)
                request.env.cr.rollback()
                
                # Do a read-only stock check to see if we should trigger the Stock Alert popup
                stock_availability = []
                has_insufficient_stock = False
                idx = 0
                while True:
                    pid = kwargs.get(f'line_product_id[{idx}]')
                    qty = kwargs.get(f'line_qty[{idx}]')
                    if not pid or not qty:
                        break
                    try:
                        qty = float(qty)
                        prod = user_env['product.product'].sudo().browse(int(pid))
                        if prod.exists():
                            quants = user_env['stock.quant'].sudo().search([
                                ('product_id', '=', prod.id),
                                ('company_id', '=', user.company_id.id),
                                ('location_id.usage', '=', 'internal')
                            ])
                            avail = sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))
                            if avail < qty:
                                has_insufficient_stock = True
                            stock_availability.append({
                                "product_id": prod.id,
                                "product_name": prod.display_name,
                                "requested_qty": qty,
                                "available_qty": avail,
                                "is_available": avail >= qty
                            })
                    except:
                        pass
                    idx += 1
                
                if has_insufficient_stock:
                    # Trigger the Mobile App's Stock Alert Popup!
                    return Response(json.dumps({
                        "success": False,
                        "message": "One or more products in your cart do not have enough stock.",
                        "stock_availability": stock_availability
                    }), content_type='application/json')
                else:
                    # Stock is fine, so it must be a Miracle timeout or genuine deadlock
                    return Response(json.dumps({
                        "success": False,
                        "message": "The server is currently processing another high-priority order for these items. Please try placing your order again in a few seconds."
                    }), content_type='application/json')
        # ---------------------------------------------

        # READ ORDER LINES
        order_lines = []
        index = 0
        
        stock_issues = []
        stock_availability = []

        while True:
            product_id = kwargs.get(f'line_product_id[{index}]')
            qty = kwargs.get(f'line_qty[{index}]')
            price = kwargs.get(f'line_price[{index}]')

            if not product_id or not qty:
                break

            try:
                qty = float(qty)
                price = float(price or 0)
            except:
                return Response(json.dumps({
                    "success": False,
                    "message": f"Invalid qty/price at line {index}"
                }), content_type='application/json')

            product = user_env['product.product'].sudo().browse(int(product_id))
            if not product.exists():
                return Response(json.dumps({
                    "success": False,
                    "message": f"Invalid product_id: {product_id}"
                }), content_type='application/json')

            # --- Check Stock Availability ---
            quants = user_env['stock.quant'].sudo().search([
                ('product_id', '=', product.id),
                ('company_id', '=', user.company_id.id),
                ('location_id.usage', '=', 'internal')
            ])
            available_qty = sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))
            
            is_available = available_qty >= qty
            
            stock_availability.append({
                "product_id": product.id,
                "product_name": product.display_name,
                "requested_qty": qty,
                "available_qty": available_qty,
                "is_available": is_available
            })
            
            if not is_available:
                stock_issues.append(product.display_name)
            # --------------------------------

            if not price:
                if user.company_id.mobile_app_pricelist_id:
                    price = user.company_id.mobile_app_pricelist_id._get_product_price(
                        product,
                        qty,
                        partner=partner
                    )
                else:
                    price = product.list_price
            
            sale_order_vals['order_line'].append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': price,
            }))

            index += 1

        if stock_issues:
            return Response(json.dumps({
                "success": False,
                "message": "One or more products in your cart do not have enough stock.",
                "stock_availability": stock_availability
            }), content_type='application/json')

        if not sale_order_vals['order_line']:
            # sale_capture.unlink()
            return Response(json.dumps({
                "success": False,
                "message": "At least one product is required"
            }), content_type='application/json')
        
        try:
            # Create the Sale Order and skip immediate Miracle sync (handled later)
            sale_order = user_env['sale.order'].sudo().with_context(skip_miracle_sync=True).create(sale_order_vals)
            
            # Automatically confirm the Quotation into a Sales Order to generate the Delivery
            sale_order.action_confirm()

            # 1. Automate Delivery Validation
            for picking in sale_order.picking_ids:
                picking.with_context(skip_miracle_sync=True).action_assign()

                for move_line in picking.move_ids:
                    move_line.quantity = move_line.product_uom_qty
                
                # Force validation by skipping popup wizards
                picking.with_context(
                    skip_miracle_sync=True, 
                    skip_immediate=True, 
                    skip_backorder=True
                ).button_validate()
                
            # 2. Automate Invoice Creation and Posting
            invoice = sale_order.with_context(skip_miracle_sync=True)._create_invoices()
            if invoice:
                invoice.with_context(skip_miracle_sync=True).action_post()

            # 3. Synchronously upload delivery to Miracle so the stock is immediately deducted
            # before the PostgreSQL lock is released for the next user!
            for picking in sale_order.picking_ids.filtered(lambda p: p.state == 'done' and p.picking_type_id.code == 'outgoing' and not p.is_miracle_voucher):
                picking.with_company(picking.company_id).with_context(skip_miracle_sync=False).action_upload_challan_to_miracle()

        except Exception as e:
            return Response(json.dumps({
                "success": False,
                "message": str(e)
            }), content_type='application/json')

        # RESPONSE
        sale_orders = []
        sale_orders.append({
            "id": sale_order.id,
            "name": sale_order.name,
            "company": sale_order.company_id.name,
            "amount_total": fmt_num(sale_order.amount_total)
        })

        return Response(json.dumps({
            "success": True,
            "message": "Order created successfully",
            "customer_id": partner.id,
            "customer_name": partner.name,
            "sale_capture_id": sale_order.id, # Using SO id directly
            "reference": sale_order.name, # Using SO name directly
            "state": sale_order.state,
            "sale_orders": sale_orders
        }), content_type='application/json')

############### API to list Sale Capture records ########################## 
class SaleCaptureListAPI(http.Controller):

    @http.route('/sale_capture_list', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_sale_capture_list(self, **kwargs):

        user, error_response = validate_api_request(request, kwargs)
        if error_response:
            return error_response

        base_url = request.httprequest.host_url.rstrip('/')

        sale_orders = request.env['sale.order'].sudo().search([('user_id', '=', user.id)], order='id desc')
        if not sale_orders:
            return Response(json.dumps({
                "success": False,
                "message": "No orders found"
            }), content_type='application/json')

        result = []

        for record in sale_orders:

            # Prepare lines
            lines = []
            for line in record.order_line:
                lines.append({
                    "product_id": line.product_id.id,
                    "product_name": line.product_id.name,
                    "qty": fmt_num(line.product_uom_qty),
                    "price": fmt_num(line.price_unit),
                    "subtotal": fmt_num(line.price_subtotal),
                    "image_url": f"{base_url}/web/image/product.template/{line.product_id.id}/image_1920??t={int(datetime.now().timestamp())}"
                })

            result.append({
                "sale_capture_id": record.id, # Using SO id directly to maintain app compatibility
                "reference": record.name,
                "customer": record.partner_id.name,
                "capture_date": str(record.date_order),
                "state": record.state,
                "grand_total": fmt_num(record.amount_total),
                "lines": lines,
            })

        return Response(json.dumps({
            "success": True,
            "total_records": len(result),
            "data": result
        }), content_type='application/json')

############### API to list Sale Orders corresponding to a Sale Capture record ########################## 
class SaleCaptureSaleOrderAPI(http.Controller):

    @http.route('/list_sale_capture_sale_orders', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_sale_orders_by_capture(self, **kwargs):

        user, error_response = validate_api_request(request, kwargs)
        if error_response:
            return error_response

        base_url = request.httprequest.host_url.rstrip('/')

        sale_capture_id = kwargs.get('sale_capture_id')

        if not sale_capture_id:
            return Response(json.dumps({
                "success": False,
                "message": "sale_capture_id is required"
            }), content_type='application/json')

        # sale_capture = request.env['sale.capture'].sudo().browse(int(sale_capture_id))
        so = request.env['sale.order'].sudo().browse(int(sale_capture_id))

        if not so.exists():
            return Response(json.dumps({
                "success": False,
                "message": "Invalid sale_capture_id (Order not found)"
            }), content_type='application/json')

        # Group Sale Orders company-wise (mimicking old structure)
        company_wise_orders = {}
        company_name = so.company_id.name

        if company_name not in company_wise_orders:
            company_wise_orders[company_name] = []

        company_wise_orders[company_name].append({
            "sale_order_id": so.id,
            "sale_order_name": so.name,
            "amount_total": fmt_num(so.amount_total),
            "state": so.state,
            "date_order": str(so.date_order),
            "products": [
                {
                    "product_id": line.product_id.id,
                    "product_name": line.product_id.name,
                    "image_url": f"{base_url}/web/image/product.template/{line.product_id.id}/image_1920??t={int(datetime.now().timestamp())}"
                }
                for line in so.order_line
            ]
        })

        return Response(json.dumps({
            "success": True,
            "sale_capture_id": so.id,
            "reference": so.name,
            "customer": so.partner_id.name,
            "company_wise_sale_orders": company_wise_orders
        }), content_type='application/json')

############### API to list single Sale Orders' Details corresponding to a Sale Capture record ########################## 
class SaleCaptureSaleOrderLineAPI(http.Controller):

    @http.route('/list_sale_order_details', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_sale_order_lines_by_capture(self, **kwargs):

        user, error_response = validate_api_request(request, kwargs)
        if error_response:
            return error_response
        
        base_url = request.httprequest.host_url.rstrip('/')
        # sale_capture_id = kwargs.get('sale_capture_id')
        sale_order_id = kwargs.get('sale_order_id') or kwargs.get('sale_capture_id')

        if not sale_order_id:
            return Response(json.dumps({
                "success": False,
                "message": "sale_order_id is required"
            }), content_type='application/json')

        # Filter specific Sale Order
        sale_order = request.env['sale.order'].sudo().browse(int(sale_order_id))

        if not sale_order.exists():
            return Response(json.dumps({
                "success": False,
                "message": "Sale Order not found"
            }), content_type='application/json')

        # Prepare order lines
        order_lines = []
        for line in sale_order.order_line:
            order_lines.append({
                "product_id": line.product_id.id,
                "product_name": line.product_id.name,
                "category": line.product_id.categ_id.name if line.product_id.categ_id else '',
                "quantity": fmt_num(line.product_uom_qty),
                "price_unit": fmt_num(line.price_unit),
                "subtotal": fmt_num(line.price_subtotal),
                "slab_applied": _get_applied_slab(sale_order, line),
                "image_url": f"{base_url}/web/image/product.template/{line.product_id.id}/image_1920??t={int(datetime.now().timestamp())}"
            })

        # Response (single SO instead of company-wise grouping)
        return Response(json.dumps({
            "success": True,
            "sale_capture_id": sale_order.id, # Fallback mapping
            "reference": sale_order.name,
            "customer": sale_order.partner_id.name,
            "sale_order": {
                "sale_order_id": sale_order.id,
                "sale_order_name": sale_order.name,
                "company": sale_order.company_id.name,
                "amount_total": fmt_num(sale_order.amount_total),
                "state": sale_order.state,
                "date_order": str(sale_order.date_order),
                "order_lines": order_lines
            }
        }), content_type='application/json')
