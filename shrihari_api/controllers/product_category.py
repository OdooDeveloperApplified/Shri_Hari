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

