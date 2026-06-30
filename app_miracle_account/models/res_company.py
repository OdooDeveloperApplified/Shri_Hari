from odoo import models, fields
from datetime import timedelta
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = "res.company"

    miracle_account_ledger_url = fields.Char("Account Ledger URL", default="TPA/M2/V1/AccountLedger", readonly=True)
    miracle_get_account_url = fields.Char("Get Account URL", default="TPA/M2/V1/GetAccount", readonly=True)
    miracle_post_account_url = fields.Char("Account Create URL", default="TPA/M2/V1/Account", readonly=True)

    def _action_get_miracle_account_ledger(self):
        _logger.info("Starting to fetch account ledger from Miracle")
        endpoint = self.miracle_account_ledger_url
        method="post"
        payload = {
            "fromdate": "2026-04-01",
            "todate": "2027-03-31",
            "rptfield": [
                "accid",
                "accnm",
                "accalinm",
                # "istcsac",
                "accgrpnm",
                "citynm",
                "areanm",
                "statenm",
                "sgrpname",
                "panno",
                "crdays",
                "crlimit",
                "aadharno",
                "gstin",
                # "accinno",
                "transport",
                "regtype",
                "udyamno",
                "udyamtyp",
                # "gstuino",
                "udyamact",
                "accstatus",
                "balmethod",
                # "catnm",
                "conper1",
                "conper2",
                "addr1",
                "addr2",
                "addr3",
                "addr4",
                "pincode",
                "mob1",
                "mob2",
                "phone1",
                "phone2",
                "rphone1",
                "rphone2",
                "factoryno",
                "email",
                "website",
                "bname",
                "bbranch",
                "bradd",
                "bifsc",
                "baccno",
                "ibanno",
                "swiftcode",
                "opbal",
                "totalcr",
                "totaldb",
                "clbal"    
            ],
            "rptfilter": {}
        }
 
        partner_data = self.miracle_api_call(endpoint, method, payload)
        resPartner = self.env['res.partner']
        _logger.info("this is partner data %s", partner_data)
        return resPartner._action_insert_miracle_account_partner(partner_data)
    
    def _action_get_miracle_account(self):
        _logger.info("Starting to fetch account ledger from Miracle")
        endpoint = self.miracle_account_ledger_url
        method="post"
        payload = {
            "fromdate": "2026-04-01",
            "todate": "2027-03-31",
            "rptfield": [
                "accid",
                # "accnm",
                # "istcsac",
                "accgrpnm",
                "sgrpname",  
            ],
            "rptfilter": {}
        }

        account_data = self.miracle_api_call(endpoint,method,payload)
        accounAccount = self.env['account.account']
        accounAccount._action_insert_miracle_accounts(account_data)
        _logger.info("this is account data %s",account_data)

    def _action_send_account_to_miracle(self,payload):
        self.ensure_one()
        request = self.miracle_api_call(self.miracle_post_account_url,"post",payload)
        return request

    def _action_get_account_from_miracle(self,payload):
        self.ensure_one()
        response = self.miracle_api_call(self.miracle_get_account_url,"get",payload)
        return response