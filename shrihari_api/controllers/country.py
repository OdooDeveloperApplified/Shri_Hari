from odoo import http,fields
from odoo.http import request, Response
from .token import validate_api_request, to_local_str, fmt_num, resolve_miracle_account, call_miracle_relay
from datetime import datetime
import json
import logging

_logger = logging.getLogger(__name__)

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

