from odoo import http,fields
from odoo.http import request, Response
from .token import validate_api_request, to_local_str, fmt_num, resolve_miracle_account, call_miracle_relay
from datetime import datetime
import json
import logging

_logger = logging.getLogger(__name__)

############### API to list product categories present in odoo databse in mobile app ##########################
class ProductCategoryAPI(http.Controller):

    @http.route('/product_category', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_category_types(self, **kwargs):
            # Common helper function for user validation
            user, error_response = validate_api_request(request, kwargs)
            if error_response:
                return error_response

            base_url = request.httprequest.host_url.rstrip('/')

            categories = request.env['product.category'].sudo().search([], order='id asc')

            if not categories:
                return Response(
                    json.dumps({
                        "success": False,
                        "message": "No product categories found"
                    }),
                    content_type='application/json'
                )

            data = [{
                'id': c.id,
                'name': c.name,
                'image_url': f"{base_url}/web/image/product.category/{c.id}/image_128?t={int(datetime.now().timestamp())}"
            } for c in categories]

            return Response(
                json.dumps({
                    'success': True,
                    'count': len(data),
                    'categories': data
                }),
                status=200,
                content_type='application/json'
            )

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
                        pricing_slabs.append({
                            "min_qty": fmt_num(item.min_quantity),
                            "price": fmt_num(slab_price),
                            "discount_type": item.compute_price,  # 'fixed' or 'percentage'
                            "single_piece_price": fmt_num(single_piece_price),
                            "discount_percent": fmt_num(item.percent_price) if item.compute_price == 'percentage' else None,
                            "discount_message": f"Buy {int(item.min_quantity)}+ at {currency_symbol}{slab_price}/box"
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
class SaleCaptureCreateAPI(http.Controller):

    @http.route('/create_sale_capture', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def create_sale_capture(self, **kwargs):

        # Validate User
        user, error_response = validate_api_request(request, kwargs)
        if error_response:
            return error_response
        
        ##### Code to select customers from contacts ###############

        # partner_obj = request.env['res.partner'].sudo()
      
        # customer_id = kwargs.get('customer_id')

        # if customer_id:
        #     # Use existing
        #     partner = partner_obj.browse(int(customer_id))
        #     if not partner.exists():
        #         return Response(json.dumps({
        #             "success": False,
        #             "message": "Invalid customer_id"
        #         }), content_type='application/json')

        # else:
        #     mobile = kwargs.get('mobile')
        #     email = kwargs.get('email')
        #     name = kwargs.get('customer_name')
        #     company_name = kwargs.get('company_name')

        #     partner = None

        #     # SEARCH LOGIC

        #     # 1. Mobile match
        #     if mobile:
        #         partner = partner_obj.search([('mobile', '=', mobile)], limit=1)

        #     # 2. Email match
        #     if not partner and email:
        #         partner = partner_obj.search([('email', '=', email)], limit=1)

        #     # 3. Name + Company match
        #     if not partner and name:
        #         if company_name:
        #             partner = partner_obj.search([
        #                 ('name', '=', name),
        #                 ('parent_id.name', '=', company_name)
        #             ], limit=1)
        #         else:
        #             partner = partner_obj.search([
        #                 ('name', '=', name),
        #                 ('parent_id', '=', False)
        #             ], limit=1)

        #     # CREATE NEW IF NOT FOUND
        #     if not partner:

        #         if not name:
        #             return Response(json.dumps({
        #                 "success": False,
        #                 "message": "customer_name is required"
        #             }), content_type='application/json')

        #         # Handle company
        #         parent_partner = None
        #         if company_name:
        #             parent_partner = partner_obj.search([
        #                 ('name', '=', company_name),
        #                 ('is_company', '=', True)
        #             ], limit=1)

        #             if not parent_partner:
        #                 parent_partner = partner_obj.create({
        #                     'name': company_name,
        #                     'is_company': True
        #                 })

        #         customer_vals = {
        #             'name': name,
        #             'parent_id': parent_partner.id if parent_partner else False,
        #             'street': kwargs.get('street'),
        #             'street2': kwargs.get('street2'),
        #             'city': kwargs.get('city'),
        #             'zip': kwargs.get('zip'),
        #             'country_id': int(kwargs.get('country_id')) if kwargs.get('country_id') else False,
        #             'state_id': int(kwargs.get('state_id')) if kwargs.get('state_id') else False,
        #             'mobile': mobile,
        #             'email': email,
        #         }
        #         partner = partner_obj.create(customer_vals)
        #         _logger.info(f"New customer created: {partner.name}")

        #     else:
        #         _logger.info(f"Existing customer used: {partner.name}")

        # ALWAYS use logged-in user's partner as customer
        partner = user.partner_id

        if not partner:
            return Response(json.dumps({
                "success": False,
                "message": "Logged-in user has no associated contact"
            }), content_type='application/json')

        # Create environment bound to the authenticated user so context (allowed_company_ids) is correct
        user_env = request.env(user=user)

        # CREATE NATIVE SALE ORDER INSTEAD (Sale Capture commented out)
        # sale_capture = user_env['sale.capture'].sudo().create({
        #     'user_id': user.id,
        #     'customer_id': partner.id,
        #     'customer_street': partner.street,
        #     'customer_street2': partner.street2,
        #     'customer_city': partner.city,
        #     'customer_zip': partner.zip,
        #     'customer_country_id': partner.country_id.id,
        #     'customer_state_id': partner.state_id.id,
        #     'customer_mobile': partner.mobile,
        #     'customer_email': partner.email,
        # })

        sale_order_vals = {
            'partner_id': partner.id,
            'user_id': user.id,
            'order_line': []
        }
        if user.company_id.mobile_app_pricelist_id:
            sale_order_vals['pricelist_id'] = user.company_id.mobile_app_pricelist_id.id

        # READ ORDER LINES
        order_lines = []
        index = 0

        while True:
            product_id = kwargs.get(f'line_product_id[{index}]')
            # _logger.info("thissssss is product_id %s",product_id)
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
            # _logger.info("thissss is product %s",product)
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
            
            if available_qty < qty:
                return Response(json.dumps({
                    "success": False,
                    "message": f"Not enough stock for product {product.display_name}. Available: {available_qty}, Requested: {qty}"
                }), content_type='application/json')
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

            # order_lines.append({
            #     'capture_id': sale_capture.id,
            #     'product_id': product.id,
            #     'product_uom_qty': qty,
            #     'price_unit': price,
            # })
            
            sale_order_vals['order_line'].append((0, 0, {
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': price,
            }))

            index += 1

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

            # 3. Trigger Background Sync Cron Job (Upload delivery to miracle)
            cron_job = request.env.ref('app_miracle_voucher.cron_sync_miracle_deliveries', raise_if_not_found=False)
            if cron_job:
                cron_job.sudo()._trigger()
            
        except Exception as e:
            return Response(json.dumps({
                "success": False,
                "message": str(e)
            }), content_type='application/json')

        # RESPONSE
        sale_orders = []
        # for so in sale_capture.sale_order_ids:
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

        # sale_captures = request.env['sale.capture'].sudo().search([], order='id desc')
        # if not sale_captures:
        #     return Response(json.dumps({
        #         "success": False,
        #         "message": "No Sale Capture records found"
        #     }), content_type='application/json')

        sale_orders = request.env['sale.order'].sudo().search([('user_id', '=', user.id)], order='id desc')
        if not sale_orders:
            return Response(json.dumps({
                "success": False,
                "message": "No orders found"
            }), content_type='application/json')

        result = []

        # for record in sale_captures:
        for record in sale_orders:

            # Prepare lines
            lines = []
            # for line in record.line_ids:
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

class CountryAPI(http.Controller):

    @http.route('/countries', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_countries(self, **kwargs):

        # Validate user
        user, error_response = validate_api_request(request, kwargs)
        if error_response:
            return error_response

        countries = request.env['res.country'].sudo().search([], order='name asc')

        if not countries:
            return Response(json.dumps({
                "success": False,
                "message": "No countries found"
            }), content_type='application/json')

        country_list = [{
            'id': country.id,
            'name': country.name,
            'code': country.code
        } for country in countries]

        return Response(json.dumps({
            "success": True,
            "total_countries": len(country_list),
            "countries": country_list
        }), content_type='application/json')

class CountryStateAPI(http.Controller):

    @http.route('/states_by_country', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_states_by_country(self, **kwargs):

        # Validate user
        user, error_response = validate_api_request(request, kwargs)
        if error_response:
            return error_response

        country_id = kwargs.get('country_id')

        if not country_id:
            return Response(json.dumps({
                "success": False,
                "message": "country_id is required"
            }), content_type='application/json')

        country = request.env['res.country'].sudo().browse(int(country_id))

        if not country.exists():
            return Response(json.dumps({
                "success": False,
                "message": "Invalid country_id"
            }), content_type='application/json')

        # Fetch states for selected country
        states = request.env['res.country.state'].sudo().search([
            ('country_id', '=', country.id)
        ])

        state_list = [{
            'id': state.id,
            'name': state.name,
            'code': state.code
        } for state in states]

        return Response(json.dumps({
            "success": True,
            "country_id": country.id,
            "country_name": country.name,
            "total_states": len(state_list),
            "states": state_list
        }), content_type='application/json')

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

    # @http.route('/account_voucher_list', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    # def get_account_voucher_list(self, **kwargs):

    #     user, company, miracle_account_id, error_response = resolve_miracle_account(request, kwargs)
    #     if error_response:
    #         return error_response

    #     # Note: Miracle's own field names for this call are camelCase
    #     # (fromDate/toDate/rptFilter), unlike AccountLedger's lowercase
    #     # (fromdate/todate/rptfilter) - kept exactly as Miracle documents
    #     # it rather than normalizing the two to match each other.
    #     from_date = kwargs.get('fromDate')
    #     to_date = kwargs.get('toDate')

    #     if not from_date or not to_date:
    #         return Response(json.dumps({
    #             "IsError": True,
    #             "ErrorCode": "MISSINGDATE",
    #             "Message": "fromDate and toDate are required."
    #         }), content_type='application/json')

    #     payload = {
    #         "fromDate": from_date,
    #         "toDate": to_date,
    #         "rptFilter": {
    #             "accid": [miracle_account_id]
    #         }
    #     }

    #     return call_miracle_relay(company, 'TPA/M2/V1/AccountVoucherList', 'post', payload)

    # @http.route('/generate_file', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    # def generate_file(self, **kwargs):

    #     user, company, miracle_account_id, error_response = resolve_miracle_account(request, kwargs)
    #     if error_response:
    #         return error_response

    #     rpt_type = kwargs.get('rptType')

    #     if rpt_type == 'RPT001':
    #         # Account Statement PDF - keyed by the caller's own account.
    #         from_date = kwargs.get('fromDate')
    #         to_date = kwargs.get('toDate')
    #         if not from_date or not to_date:
    #             return Response(json.dumps({
    #                 "IsError": True,
    #                 "ErrorCode": "MISSINGDATE",
    #                 "Message": "fromDate and toDate are required for RPT001."
    #             }), content_type='application/json')
    #         payload = {
    #             "rptType": "RPT001",
    #             "uniqueId": miracle_account_id,
    #             "fromDate": from_date,
    #             "toDate": to_date,
    #         }

    #     elif rpt_type == 'RPT002':
    #         # Ageing / Outstanding Report PDF - also keyed by the account.
    #         report_date = kwargs.get('reportDate')
    #         if not report_date:
    #             return Response(json.dumps({
    #                 "IsError": True,
    #                 "ErrorCode": "MISSINGDATE",
    #                 "Message": "reportDate is required for RPT002."
    #             }), content_type='application/json')
    #         payload = {
    #             "rptType": "RPT002",
    #             "uniqueId": miracle_account_id,
    #             "reportDate": report_date,
    #         }

    #     elif rpt_type == 'RPT003':
    #         # Voucher / Invoice Print PDF - keyed by a VOUCHER id, not an
    #         # account id. Trusted as sent by the app, same accepted-risk
    #         # basis as miracle_account_id elsewhere in this file - see
    #         # resolve_miracle_account()'s docstring for the reasoning and
    #         # where to add a check later if this ever needs closing.
    #         voucher_id = kwargs.get('voucher_id') or kwargs.get('uniqueId')
    #         if not voucher_id:
    #             return Response(json.dumps({
    #                 "IsError": True,
    #                 "ErrorCode": "MISSINGVOUCHER",
    #                 "Message": "voucher_id is required for RPT003."
    #             }), content_type='application/json')
    #         payload = {
    #             "rptType": "RPT003",
    #             "uniqueId": voucher_id,
    #         }

    #     else:
    #         return Response(json.dumps({
    #             "IsError": True,
    #             "ErrorCode": "BADRPTTYPE",
    #             "Message": "rptType must be one of RPT001, RPT002, RPT003."
    #         }), content_type='application/json')

    #     return call_miracle_relay(company, 'TPA/M2/V1/GenerateFile', 'post', payload)


