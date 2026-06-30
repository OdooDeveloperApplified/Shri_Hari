from odoo import fields, models
from odoo.exceptions import UserError
import requests
import logging
_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    miracle_base_url = fields.Char(related="company_id.miracle_base_url", readonly=False)
    miracle_authapi = fields.Char(related="company_id.miracle_authapi", readonly=False)
    miracle_urlkey = fields.Char(related="company_id.miracle_urlkey", readonly=False)
    miracle_clientid = fields.Char(related="company_id.miracle_clientid", readonly=False)
    miracle_apikey = fields.Char(related="company_id.miracle_apikey", readonly=False)
    miracle_access_token = fields.Text(related="company_id.miracle_access_token", readonly=True
    )
    miracle_token_generated_at = fields.Datetime(
        related="company_id.miracle_token_generated_at",
        readonly=True
    )
    miracle_token_expiry = fields.Datetime(
        related="company_id.miracle_token_expiry",
        readonly=True
    )

    def action_generate_miracle_token(self):
        self.ensure_one()
        company = self.company_id
        company.action_generate_miracle_token()

        # if not company.miracle_base_url:
        #     raise UserError("Please configure Base URL first.")

        # # Build URL with query parameter
        # url = f"{company.miracle_base_url.rstrip('/')}/{company.miracle_authapi}"
        # params = {"urlKey": company.miracle_urlkey}

        # # Set headers
        # headers = {"clientId": company.miracle_clientid, "apiKey": company.miracle_apikey}

        # try:
        #     response = requests.post(
        #         url, headers=headers, params=params, verify=False
        #     )
        #     response.raise_for_status()
        #     data = response.json()
        #     _logger.info("response %s", data)

        #     access_token = data.get("DataModel", {}).get("token")
        #     if not access_token:
        #         raise UserError("Token not found in response.")

        #     company.miracle_access_token = access_token

        # except Exception as e:
        #     raise UserError("Token generation failed:\n%s" % str(e))
