from odoo import models, fields , api
import requests
from datetime import timedelta
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = "res.company"

    miracle_base_url = fields.Char("Miracle Cloud ERP Base URL")
    miracle_authapi = fields.Char("Auth API",default="CLAuth/Authenticate")
    miracle_urlkey = fields.Char("Miracle URL Key")
    miracle_clientid = fields.Char("Miracle Client ID")
    miracle_apikey = fields.Char("Miracle API Key")
    miracle_access_token = fields.Text(string="Access Token",readonly=True)
    miracle_token_generated_at = fields.Datetime("Token Generated At")
    miracle_token_expiry = fields.Datetime("Token Expiry")

    miracle_session_count = fields.Integer(
        compute="_compute_session_count",
        string="Token Sessions",
    )
    sync_to_another_companies = fields.Boolean(
        string="Sync Masters To Other Miracle Companies"
    )
    sync_target_company_ids = fields.Many2many(
        'res.company',
        'res_company_sync_rel',
        'source_company_id',
        'target_company_id',
        string="Sync To Miracle Companies",
        domain="[('id', '!=', id)]"
    )

    def _compute_session_count(self):
        for rec in self:
            rec.miracle_session_count = self.env[
                "miracle.token.session"
            ].search_count([("company_id", "=", rec.id)])

    def miracle_notification(self, message, notif_type="success", sticky=False):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'message': message,
                'type': notif_type,
                'sticky': sticky
            }
        }


    # # 🔥 BUTTON METHOD
    # def action_generate_miracle_token(self):
    #     self.ensure_one()
    #     company = self.env.company

    #     if not company.miracle_base_url:
    #         raise UserError("Please configure Base URL first.")

    #     # Build URL with query parameter
    #     url = f"{company.miracle_base_url.rstrip('/')}/{company.miracle_authapi}"
    #     params = {
    #         "urlKey": company.miracle_urlkey
    #     }

    #     # Set headers
    #     headers = {
    #         "clientId": company.miracle_clientid,
    #         "apiKey": company.miracle_apikey
    #     }

    #     try:
    #         response = response = requests.post(url, headers=headers, params=params, verify=False)
            
    #         response.raise_for_status()
    #         data = response.json()
    #         _logger.info("response %s", data)

    #         access_token = data.get("DataModel", {}).get("token")
    #         if not access_token:
    #             raise UserError("Token not found in response.")

    #         company.miracle_access_token = access_token

    #     except Exception as e:
    #         raise UserError(("Token generation failed:\n%s") % str(e))

    # =========================
    # Generate Token
    # =========================
    # def action_generate_miracle_token(self):
    #     self.ensure_one()

    #     if not self.miracle_base_url:
    #         raise UserError("Please configure Base URL first.")

    #     url = "%s/%s" % (
    #         self.miracle_base_url.rstrip("/"),
    #         self.miracle_authapi,
    #     )

    #     params = {"urlKey": self.miracle_urlkey}
    #     headers = {
    #         "clientId": self.miracle_clientid,
    #         "apiKey": self.miracle_apikey,
    #     }

    #     try:
    #         response = requests.post(
    #             url,
    #             headers=headers,
    #             params=params,
    #             timeout=30,
    #             verify=False,
    #         )
    #         response.raise_for_status()
    #         data = response.json()

    #         token = data.get("DataModel", {}).get("token")
    #         if not token:
    #             raise UserError("Token not found in response.")

    #         now = fields.Datetime.now()
    #         expiry = now + timedelta(minutes=20)

    #         # Save current state
    #         self.write({
    #             "miracle_access_token": token,
    #             "miracle_token_generated_at": now,
    #             "miracle_token_expiry": expiry,
    #         })

    #         # Log token generation
    #         self.env["miracle.api.log"].create({
    #             "company_id": self.id,
    #             "name": "Token Generation",
    #             "token": token,
    #             "token_generated_at": now,
    #             "request_url": url,
    #             "request_method": "post",
    #             "response_payload": str(data),
    #             "status": "success",
    #             "response_code": response.status_code,
    #         })

    #         return token

    #     except Exception as e:
    #         self.env["miracle.api.log"].create({
    #             "company_id": self.id,
    #             "name": "Token Generation Failed",
    #             "request_url": url,
    #             "request_method": "post",
    #             "response_payload": str(e),
    #             "status": "failed",
    #         })
    #         raise UserError("Token generation failed:\n%s" % str(e))

    # # =========================
    # # Get Valid Token
    # # =========================
    # def _get_valid_miracle_token(self):
    #     self.ensure_one()
    #     now = fields.Datetime.now()

    #     if (
    #         not self.miracle_access_token
    #         or not self.miracle_token_expiry
    #         or now >= self.miracle_token_expiry
    #     ):
    #         _logger.info("Miracle token expired or missing. Regenerating.")
    #         return self.action_generate_miracle_token()

    #     return self.miracle_access_token

    # # =========================
    # # Centralized API Wrapper
    # # =========================
    # def miracle_api_call(self, endpoint, method="post", payload=None):
    #     """
    #     Always use this method for Miracle API calls
    #     """
    #     self.ensure_one()

    #     token = self._get_valid_miracle_token()

    #     url = "%s/%s" % (
    #         self.miracle_base_url.rstrip("/"),
    #         endpoint,
    #     )

    #     headers = {
    #         "Authorization": "Bearer %s" % token,
    #         "Content-Type": "application/json",
    #     }

    #     try:
    #         response = requests.request(
    #             method,
    #             url,
    #             headers=headers,
    #             json=payload,
    #             timeout=30,
    #             verify=False,
    #         )

    #         data = {}
    #         try:
    #             data = response.json()
    #         except Exception:
    #             data = response.text

    #         # Log API call
    #         self.env["miracle.api.log"].create({
    #             "company_id": self.id,
    #             "name": "API Call - %s" % endpoint,
    #             "token": token,
    #             "token_generated_at": self.miracle_token_generated_at,
    #             "request_url": url,
    #             "request_method": method,
    #             "request_payload": str(payload),
    #             "response_payload": str(data),
    #             "status": "success" if response.ok else "failed",
    #             "response_code": response.status_code,
    #         })

    #         response.raise_for_status()
    #         return data

    #     except Exception as e:
    #         self.env["miracle.api.log"].create({
    #             "company_id": self.id,
    #             "name": "API Call Failed - %s" % endpoint,
    #             "token": token,
    #             "request_url": url,
    #             "request_method": method,
    #             "request_payload": str(payload),
    #             "response_payload": str(e),
    #             "status": "failed",
    #         })
    #         raise

    # ========================================
    # Generate Token (Create Session)
    # ========================================
    @api.model
    def _cron_refresh_miracle_tokens(self):
        """Automatically refresh Miracle tokens every 15 mins via scheduled action."""
        companies = self.search([('miracle_base_url', '!=', False), ('miracle_clientid', '!=', False)])
        for company in companies:
            try:
                company.action_generate_miracle_token()
                _logger.info("Cron: Successfully refreshed Miracle token for company %s", company.name)
            except Exception as e:
                _logger.error("Cron: Failed to refresh Miracle token for company %s: %s", company.name, str(e))

    def action_generate_miracle_token(self):
        self.ensure_one()

        if not self.miracle_base_url:
            raise UserError("Configure Base URL first.")

        url = "%s/%s" % (
            self.miracle_base_url.rstrip("/"),
            self.miracle_authapi,
        )

        headers = {
            "clientId": self.miracle_clientid,
            "apiKey": self.miracle_apikey,
        }

        params = {"urlKey": self.miracle_urlkey}

        response = requests.post(
            url,
            headers=headers,
            params=params,
            timeout=30,
            verify=False,
        )

        response.raise_for_status()
        data = response.json()

        token = data.get("DataModel", {}).get("token")
        if not token:
            raise UserError("Token not found.")

        now = fields.Datetime.now()
        expiry = now + timedelta(minutes=20)

        # Expire previous active session
        old_session = self.env["miracle.token.session"].search([
            ("company_id", "=", self.id),
            ("state", "=", "active"),
        ])
        if old_session:
            old_session.write({"state": "expired"})

        # Create new session
        session = self.env["miracle.token.session"].create({
            "company_id": self.id,
            "token": token,
            "generated_at": now,
            "expiry_at": expiry,
        })

        # Update latest snapshot
        self.write({
            "miracle_access_token": token,
            "miracle_token_generated_at": now,
            "miracle_token_expiry": expiry,
        })

        return token

    # ========================================
    # Get Valid Token
    # ========================================
    def _get_valid_session(self):
        self.ensure_one()

        now = fields.Datetime.now()

        session = self.env["miracle.token.session"].search([
            ("company_id", "=", self.id),
            ("state", "=", "active"),
        ], limit=1)

        if not session or now >= session.expiry_at:
            if session:
                session.write({"state": "expired"})
            self.action_generate_miracle_token()
            session = self.env["miracle.token.session"].search([
                ("company_id", "=", self.id),
                ("state", "=", "active"),
            ], limit=1)

        return session

    # ========================================
    # Centralized API Wrapper
    # ========================================
    def miracle_api_call(self, endpoint, method="post", payload=None):
        self.ensure_one()

        session = self._get_valid_session()
        token = session.token

        url = "%s/%s" % (
            self.miracle_base_url.rstrip("/"),
            endpoint,
        )

        headers = {
            "Authorization": "Bearer %s" % token,
            "Content-Type": "application/json",
        }

        #added this if else method for get and post URL
        if method.lower() == "get":
            response = requests.request(
                method,
                url,
                headers=headers,
                params=payload,
                timeout=30,
                verify=False
            )

        else:
            response = requests.request(
                method,
                url,
                headers=headers,
                json=payload,
                timeout=30,
                verify=False,
            )

        try:
            data = response.json()
            _logger.info("this is response of api call %s", data)
        except Exception:
            data = response.text

        self.env["miracle.api.log"].create({
            "session_id": session.id,
            "company_id": self.id,
            "name": endpoint,
            "request_url": url,
            "request_method": method,
            "request_payload": str(payload),
            "response_payload": str(data),
            "response_code": response.status_code,
            "status": "success" if response.ok else "failed",
        })

        response.raise_for_status()

        return data
    

    # def get_product(self):
    #     _logger.info("this is get product call")
    #     endpoint = "TPA/M2/V1/ProductLedger"
    #     method="post"
    #     payload= {
    #         "fromdate": "2025-04-01",
    #         "todate": "2026-03-31",
    #         "rptfield": ["prdnm","prdid","slabnm","hsncode","opqty1","recqty1","iqty1","clqty1"],
    #         # "rptfilter": {
    #         #     #"prdnm":["SAI PARADO NKS"]
    #         #     #"slabnm":[""]
    #         #     #"prdid": ["6aadb8b57f"]
    #         #     #"grpnm":["RAJESH PLASTIC"]
    #         #     #"hsncode":[""]
    #         # }

    #     }
 
    #     product_data = self.miracle_api_call(endpoint, method, payload)
    #     _logger.info("this i sproduct data %s", product_data)