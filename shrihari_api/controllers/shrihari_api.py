from odoo import http,fields
from odoo.http import request, Response
from .token import validate_api_request
from datetime import datetime
import json
import logging

_logger = logging.getLogger(__name__)

############### API to list all Contacts ##########################
# class ContactListAPI(http.Controller):

#     @http.route('/contacts', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
#     def get_contacts(self, **kwargs):

#         # Validate user
#         user, error_response = validate_api_request(request, kwargs)
#         if error_response:
#             return error_response

#         partners = request.env['res.partner'].sudo().search([], order='id asc')

#         if not partners:
#             return Response(
#                 json.dumps({
#                     "success": False,
#                     "message": "No contacts found"
#                 }),
#                 content_type='application/json'
#             )

#         data = []
#         for partner in partners:
#             data.append({
#                 "id": partner.id,
#                 "name": partner.name,
#                 "company_name": partner.parent_id.name if partner.parent_id else '',
#                 "is_company": partner.is_company,
#                 "mobile": partner.mobile,
#                 "phone": partner.phone,
#                 "email": partner.email,
#                 "street": partner.street,
#                 "street2": partner.street2,
#                 "city": partner.city,
#                 "zip": partner.zip,
#                 "country": partner.country_id.name if partner.country_id else '',
#                 "state": partner.state_id.name if partner.state_id else '',
#                 "gstin": partner.vat or '',  # useful for India
#             })

#         return Response(
#             json.dumps({
#                 "success": True,
#                 "total_contacts": len(data),
#                 "contacts": data
#             }),
#             status=200,
#             content_type='application/json'
#         )

############### API to list product categories present in odoo databse in mobile app ##########################
class ProductCategoryAPI(http.Controller):

    @http.route('/product_category', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_category_types(self, **kwargs):
            # Common helper function for user validation
            user, error_response = validate_api_request(request, kwargs)
            if error_response:
                return error_response

            categories = request.env['product.category'].sudo().search([])

            if not categories:
                return Response(
                    json.dumps({
                        "success": False,
                        "message": "No product categories found"
                    }),
                    content_type='application/json'
                )

            data = [{'id': c.id,'name': c.name} for c in categories]

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
        
        if not category_id:
            return Response(
                json.dumps({
                    "success": False,
                    "message": "category_id is required"
                }),
                status=400,
                content_type='application/json'
            )
        
        category = request.env['product.category'].sudo().browse(int(category_id))
        if not category.exists():
            return Response(
                json.dumps({
                    "success": False,
                    "message": "Invalid category_id"
                }),
                content_type='application/json'
            )
        
        # Fetch products for the given category (including child categories)
        products = request.env['product.template'].sudo().search([
            ('categ_id', 'child_of', category.id)
        ])

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
            
            domain = [
                '|', ('product_tmpl_id', '=', product.id),
                     ('product_id', '=', product.product_variant_id.id),
                ('min_quantity', '>', 1)
            ]
            
            # If a global pricelist is configured in settings, restrict slabs to only that pricelist
            if company.mobile_app_pricelist_id:
                domain.append(('pricelist_id', '=', company.mobile_app_pricelist_id.id))
            
            pricelist_items = request.env['product.pricelist.item'].sudo().search(domain, order='min_quantity asc')
            # _logger.info("this is pricelist iteams %s and its name %s",pricelist_items, pricelist_items.name)
            
            for item in pricelist_items:
                if item.compute_price == 'fixed':
                    slab_price = item.fixed_price
                elif item.compute_price == 'percentage':
                    slab_price = product.list_price * (1 - (item.percent_price / 100.0))
                else:
                    slab_price = product.list_price # Fallback
                    
                if slab_price > 0:
                    pricing_slabs.append({
                        "min_qty": item.min_quantity,
                        "price": round(slab_price, 2),
                        "discount_message": f"Buy {int(item.min_quantity)}+ at ₹{round(slab_price, 2)}/box"
                    })
                # _logger.info("this are pricing slabs-------> %s",pricing_slabs)

            product_list.append({
                # 'id': product.id,
                'id': product.product_variant_id.id,
                'name': product.name,
                'default_code': product.default_code or '',
                'list_price': product.list_price,
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
                'free_qty': free_qty,
                'best_company': company.name,
                'uom': product.uom_id.name if product.uom_id else '',
                'category': product.categ_id.name if product.categ_id else '',
                'pricing_slabs': pricing_slabs,
                'image_url': f"{base_url}/web/image/product.template/{product.id}/image_1920??t={int(datetime.now().timestamp())}" ##### Code for product image #########
            })
            # _logger.info("this is product list %s",product_list)

        return Response(
            json.dumps({
                "success": True,
                "category_id": category.id,
                "category_name": category.name,
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

        # CREATE SALE CAPTURE
        sale_capture = user_env['sale.capture'].sudo().create({
            'user_id': user.id,
            'customer_id': partner.id,
            'customer_street': partner.street,
            'customer_street2': partner.street2,
            'customer_city': partner.city,
            'customer_zip': partner.zip,
            'customer_country_id': partner.country_id.id,
            'customer_state_id': partner.state_id.id,
            'customer_mobile': partner.mobile,
            'customer_email': partner.email,
        })

        # READ ORDER LINES
        order_lines = []
        index = 0

        while True:
            product_id = kwargs.get(f'line_product_id[{index}]')
            _logger.info("thissssss is product_id %s",product_id)
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
            _logger.info("thissss is product %s",product)
            if not product.exists():
                return Response(json.dumps({
                    "success": False,
                    "message": f"Invalid product_id: {product_id}"
                }), content_type='application/json')

            if not price:
                price = product.list_price

            order_lines.append({
                'capture_id': sale_capture.id,
                'product_id': product.id,
                'product_uom_qty': qty,
                'price_unit': price,
                
            })

            index += 1

        if not order_lines:
            sale_capture.unlink()
            return Response(json.dumps({
                "success": False,
                "message": "At least one product is required"
            }), content_type='application/json')

        # CREATE LINES
        user_env['sale.capture.line'].sudo().create(order_lines)

        # CREATE SALE ORDERS
        try:
            sale_capture.action_create_sale_orders()
        except Exception as e:
            sale_capture.unlink()
            return Response(json.dumps({
                "success": False,
                "message": str(e)
            }), content_type='application/json')

        # RESPONSE
        sale_orders = []
        for so in sale_capture.sale_order_ids:
            sale_orders.append({
                "id": so.id,
                "name": so.name,
                "company": so.company_id.name,
                "amount_total": so.amount_total
            })

        return Response(json.dumps({
            "success": True,
            "message": "Sale Capture created successfully",
            "customer_id": partner.id,
            "customer_name": partner.name,
            "sale_capture_id": sale_capture.id,
            "reference": sale_capture.name,
            "state": sale_capture.state,
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

        sale_captures = request.env['sale.capture'].sudo().search([], order='id desc')

        if not sale_captures:
            return Response(json.dumps({
                "success": False,
                "message": "No Sale Capture records found"
            }), content_type='application/json')

        result = []

        for record in sale_captures:

            # Prepare lines
            lines = []
            for line in record.line_ids:
                lines.append({
                    "product_id": line.product_id.id,
                    "product_name": line.product_id.name,
                    "qty": line.product_uom_qty,
                    "price": line.price_unit,
                    "subtotal": line.price_subtotal,
                    "image_url": f"{base_url}/web/image/product.template/{line.product_id.id}/image_1920??t={int(datetime.now().timestamp())}"
                })

            # Group Sale Orders company-wise
            # company_wise_orders = {}

            # for so in record.sale_order_ids:
            #     company_name = so.company_id.name

            #     if company_name not in company_wise_orders:
            #         company_wise_orders[company_name] = []

            #     company_wise_orders[company_name].append({
            #         "sale_order_id": so.id,
            #         "sale_order_name": so.name,
            #         "amount_total": so.amount_total,
            #         "state": so.state
            #     })

            result.append({
                "sale_capture_id": record.id,
                "reference": record.name,
                "customer": record.customer_id.name,
                "capture_date": str(record.capture_date),
                "state": record.state,
                "lines": lines,
                # "company_wise_sale_orders": company_wise_orders
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

        sale_capture = request.env['sale.capture'].sudo().browse(int(sale_capture_id))

        if not sale_capture.exists():
            return Response(json.dumps({
                "success": False,
                "message": "Invalid sale_capture_id"
            }), content_type='application/json')

        # (Optional) Restrict user access — if needed
        # if sale_capture.create_uid.id != user.id:
        #     return Response(json.dumps({
        #         "success": False,
        #         "message": "You are not authorized to view this record"
        #     }), content_type='application/json')

        if not sale_capture.sale_order_ids:
            return Response(json.dumps({
                "success": True,
                "message": "No Sale Orders found for this Sale Capture",
                "data": []
            }), content_type='application/json')

        # Group Sale Orders company-wise
        company_wise_orders = {}

        for so in sale_capture.sale_order_ids:
            company_name = so.company_id.name

            if company_name not in company_wise_orders:
                company_wise_orders[company_name] = []

            company_wise_orders[company_name].append({
                "sale_order_id": so.id,
                "sale_order_name": so.name,
                "amount_total": so.amount_total,
                "state": so.state,
                "date_order": str(so.date_order),
                # Code to show product image on App captured sale order
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
            "sale_capture_id": sale_capture.id,
            "reference": sale_capture.name,
            "customer": sale_capture.customer_id.name,
            "company_wise_sale_orders": company_wise_orders
        }), content_type='application/json')

############### API to list both Sale Orders' Details corresponding to a Sale Capture record ########################## 
# class SaleCaptureSaleOrderLineAPI(http.Controller):

#     @http.route('/list_both_sale_order_details', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
#     def get_sale_order_lines_by_capture(self, **kwargs):

#         user, error_response = validate_api_request(request, kwargs)
#         if error_response:
#             return error_response

#         sale_capture_id = kwargs.get('sale_capture_id')

#         if not sale_capture_id:
#             return Response(json.dumps({
#                 "success": False,
#                 "message": "sale_capture_id is required"
#             }), content_type='application/json')

#         sale_capture = request.env['sale.capture'].sudo().browse(int(sale_capture_id))

#         if not sale_capture.exists():
#             return Response(json.dumps({
#                 "success": False,
#                 "message": "Invalid sale_capture_id"
#             }), content_type='application/json')

#         if not sale_capture.sale_order_ids:
#             return Response(json.dumps({
#                 "success": True,
#                 "message": "No Sale Orders found",
#                 "data": []
#             }), content_type='application/json')

#         # Company-wise grouping with order lines
#         company_wise_data = {}

#         for so in sale_capture.sale_order_ids:
#             company_name = so.company_id.name

#             if company_name not in company_wise_data:
#                 company_wise_data[company_name] = []

#             # Prepare order lines
#             order_lines = []
#             for line in so.order_line:
#                 order_lines.append({
#                     "product_id": line.product_id.id,
#                     "product_name": line.product_id.name,
#                     "category": line.product_id.categ_id.name if line.product_id.categ_id else '',
#                     "quantity": line.product_uom_qty,
#                     "price_unit": line.price_unit,
#                     "subtotal": line.price_subtotal
#                 })

#             company_wise_data[company_name].append({
#                 "sale_order_id": so.id,
#                 "sale_order_name": so.name,
#                 "amount_total": so.amount_total,
#                 "state": so.state,
#                 "date_order": str(so.date_order),
#                 "order_lines": order_lines
#             })

#         return Response(json.dumps({
#             "success": True,
#             "sale_capture_id": sale_capture.id,
#             "reference": sale_capture.name,
#             "customer": sale_capture.customer_id.name,
#             "company_wise_orders": company_wise_data
#         }), content_type='application/json')

############### API to list single Sale Orders' Details corresponding to a Sale Capture record ########################## 
class SaleCaptureSaleOrderLineAPI(http.Controller):

    @http.route('/list_sale_order_details', type='http', auth='public', cors='*', methods=['POST'], csrf=False)
    def get_sale_order_lines_by_capture(self, **kwargs):

        user, error_response = validate_api_request(request, kwargs)
        if error_response:
            return error_response
        
        base_url = request.httprequest.host_url.rstrip('/')
        sale_capture_id = kwargs.get('sale_capture_id')
        sale_order_id = kwargs.get('sale_order_id')

        if not sale_capture_id:
            return Response(json.dumps({
                "success": False,
                "message": "sale_capture_id is required"
            }), content_type='application/json')

        if not sale_order_id:
            return Response(json.dumps({
                "success": False,
                "message": "sale_order_id is required"
            }), content_type='application/json')

        sale_capture = request.env['sale.capture'].sudo().browse(int(sale_capture_id))

        if not sale_capture.exists():
            return Response(json.dumps({
                "success": False,
                "message": "Invalid sale_capture_id"
            }), content_type='application/json')

        # Filter specific Sale Order
        sale_order = request.env['sale.order'].sudo().browse(int(sale_order_id))

        if not sale_order.exists() or sale_order not in sale_capture.sale_order_ids:
            return Response(json.dumps({
                "success": False,
                "message": "Sale Order not found for given Sale Capture"
            }), content_type='application/json')

        # Prepare order lines
        order_lines = []
        for line in sale_order.order_line:
            order_lines.append({
                "product_id": line.product_id.id,
                "product_name": line.product_id.name,
                "category": line.product_id.categ_id.name if line.product_id.categ_id else '',
                "quantity": line.product_uom_qty,
                "price_unit": line.price_unit,
                "subtotal": line.price_subtotal,
                "image_url": f"{base_url}/web/image/product.template/{line.product_id.id}/image_1920??t={int(datetime.now().timestamp())}"
            })

        # Response (single SO instead of company-wise grouping)
        return Response(json.dumps({
            "success": True,
            "sale_capture_id": sale_capture.id,
            "reference": sale_capture.name,
            "customer": sale_capture.customer_id.name,
            "sale_order": {
                "sale_order_id": sale_order.id,
                "sale_order_name": sale_order.name,
                "company": sale_order.company_id.name,
                "amount_total": sale_order.amount_total,
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

        data = [{
            "id": company.id,
            "name": company.name,
            "icon": "business",
            "CLIENT_ID": company.miracle_clientid or "",
            "API_KEY": company.miracle_apikey or "",
            "ACCID": partner.miracle_account_id or "",
            "MIRACLE_BASE_URL": company.miracle_base_url or "",
            "URL_KEY": company.miracle_urlkey or ""
        }]

        return Response(json.dumps({
            "success": True,
            "data": data
        }), content_type='application/json')


