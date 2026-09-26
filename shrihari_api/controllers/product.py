from odoo import http,fields
from odoo.http import request, Response
from .token import validate_api_request, to_local_str, fmt_num, resolve_miracle_account, call_miracle_relay
from datetime import datetime
import json
import logging

_logger = logging.getLogger(__name__)

############### API to list product as per the category choosen ##########################
class ProductAPI(http.Controller):

    @http.route('/products_by_category', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_products_by_category(self, **kwargs):

        user, error_response = validate_api_request(request, kwargs)
        if error_response:
            return error_response
        
        ######### Code for for product image:starts #########
        base_url = request.httprequest.host_url.rstrip('/')
        ######### Code for for product image:ends #########

        category_id = kwargs.get('category_id')
        
        domain = []
        category = None
        
        if category_id:
            try:
                category = request.env['product.category'].sudo().browse(int(category_id))
                if not category.exists():
                    return Response(
                        json.dumps({
                            "success": False,
                            "message": "Invalid category_id"
                        }),
                        content_type='application/json'
                    )
                domain = [('categ_id', 'child_of', category.id)]
            except ValueError:
                return Response(
                    json.dumps({
                        "success": False,
                        "message": "category_id must be an integer"
                    }),
                    status=400,
                    content_type='application/json'
                )
        
        # Fetch products for the given category (including child categories) or all products if no category_id
        products = request.env['product.template'].sudo().search(domain)

        # --- LIVE STOCK SYNC FOR MOBILE REFRESH ---
        try:
            if category_id:
                # Targeted sync: lightning fast for single category refresh
                miracle_ids = [p.miracle_product_id for p in products if p.miracle_product_id]
                if miracle_ids:
                    user.company_id._action_get_miracle_stock_ledger(miracle_product_ids=miracle_ids)
            else:
                # Full sync: if they pull to refresh the entire catalog
                user.company_id._action_get_miracle_stock_ledger()
        except Exception as e:
            _logger.warning("Miracle stock ledger refresh failed in products_by_category: %s", e)
        # ------------------------------------------


        # Use the single default company for the user
        company = user.company_id or request.env.company
        StockQuant = request.env['stock.quant']

        product_list = []
        for product in products:

            # Check stock for the single company
            quants = StockQuant.with_company(company).sudo().search([
                ('product_id', '=', product.product_variant_id.id),
                ('company_id', '=', company.id),
                ('location_id.usage', '=', 'internal')
            ])

            total_qty = sum(quants.mapped('quantity'))
            reserved_qty = sum(quants.mapped('reserved_quantity'))

            free_qty = total_qty - reserved_qty

            # Fetch ALL global pricing slabs for this product (ignoring user's specific pricelist)
            # This ensures all 3000+ contacts get the offers automatically.
            pricing_slabs = []
            
            # If a global pricelist is configured in settings, fetch its slabs.
            # If empty, do not fetch any slabs (pricing_slabs will be empty).
            if company.mobile_app_pricelist_id:
                slab_domain = [
                    '|', ('product_tmpl_id', '=', product.id),
                         ('product_id', '=', product.product_variant_id.id),
                    ('min_quantity', '>', 1),
                    ('pricelist_id', '=', company.mobile_app_pricelist_id.id)
                ]
                
                pricelist_items = request.env['product.pricelist.item'].sudo().search(slab_domain, order='min_quantity asc')
                # _logger.info("this is pricelist iteams %s and its name %s",pricelist_items, pricelist_items.name)

                currency_symbol = company.currency_id.symbol or ''
                pack_size = request.env['product.template']._get_miracle_pack_size(product.uom_id)
                for item in pricelist_items:
                    # Single source of truth for slab pricing: the same
                    # method Odoo uses to price a real order line off this
                    # pricelist (see shrihari_sales/models/product_pricelist_item.py)
                    # so the catalog can never show a different number than
                    # what an actual order gets charged.
                    slab_price = item._compute_price(product, item.min_quantity, product.uom_id, fields.Date.today())

                    single_piece_price = None
                    if item.compute_price == 'fixed':
                        single_piece_price = item.fixed_price
                    elif item.compute_price == 'percentage' and product.miracle_mrp:
                        single_piece_price = product.miracle_mrp

                    if slab_price > 0:
                        # Discounted per-piece price (not the plain
                        # single_piece_price field above, which is the
                        # undiscounted MRP for percentage rules) - what the
                        # message should actually advertise to the customer.
                        piece_price = slab_price / pack_size if pack_size else slab_price
                        pricing_slabs.append({
                            "min_qty": fmt_num(item.min_quantity),
                            "price": fmt_num(slab_price),
                            "discount_type": item.compute_price,  # 'fixed' or 'percentage'
                            "single_piece_price": fmt_num(single_piece_price),
                            "discount_percent": fmt_num(item.percent_price) if item.compute_price == 'percentage' else None,
                            "discount_message": f"Buy {int(item.min_quantity)}+ at {currency_symbol}{fmt_num(piece_price)}/piece"
                        })
                    # _logger.info("this are pricing slabs-------> %s",pricing_slabs)

            product_list.append({
                # 'id': product.id,
                'id': product.product_variant_id.id,
                'name': product.name,
                'default_code': product.default_code or '',
                'list_price': fmt_num(product.list_price),
                'miracle_cart_rate': fmt_num(product.miracle_single_pc_rate),
                'miracle_mrp': fmt_num(product.miracle_mrp),
                'taxes': [
                        {
                            'id': tax.id,
                            'name': tax.name,
                            # 'amount': tax.amount,
                            # 'amount_type': tax.amount_type,
                        }
                        for tax in product.taxes_id if tax.type_tax_use == 'sale'
                    ],
                # 'qty_available': product.qty_available,
                'free_qty': fmt_num(free_qty),
                'best_company': company.name,
                'uom': product.uom_id.name if product.uom_id else '',
                'uom_qty': fmt_num(product._get_miracle_pack_size(product.uom_id)),
                'category': product.categ_id.name if product.categ_id else '',
                'pricing_slabs': pricing_slabs,
                'image_url': f"{base_url}/web/image/product.template/{product.id}/image_1920??t={int(datetime.now().timestamp())}" ##### Code for product image #########
            })
            # _logger.info("this is product list %s",product_list)

        return Response(
            json.dumps({
                "success": True,
                "category_id": category.id if category else None,
                "category_name": category.name if category else "All Products",
                "total_products": len(product_list),
                "products": product_list
            }),
            status=200,
            content_type='application/json'
        )

############### API to create Sale Capture records ##########################  
