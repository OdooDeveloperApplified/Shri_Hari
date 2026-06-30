from odoo import fields, models
import logging
_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'

    miracle_post_voucher_url = fields.Char("Voucher Create URL", default="TPA/M2/V1/Voucher", readonly=True)
    miracle_get_voucher_url = fields.Char("Get Voucher URL", default="TPA/M2/V1/GetVoucher", readonly=True)

    def _action_send_voucher_to_miracle(self,payload):
        self.ensure_one()
        request = self.miracle_api_call(self.miracle_post_voucher_url,"post",payload)
        return request

    def _action_get_voucher_from_miracle(self, payload):
        self.ensure_one()
        response = self.miracle_api_call(self.miracle_get_voucher_url,"get",payload)
        return response
    
    # def _action_get_miracle_voucher(self):
    #     _logger.info("Starting to fetch account ledger from Miracle")
    #     endpoint = "TPA/M2/V1/Voucher"
    #     method="post"
    #     payload = {
    #         "fromdate": "2025-04-01",
    #         "todate": "2026-03-31",
    #         "rptfield": [
                
    #         ],
    #         "rptfilter": {}
    #     }
 
    #     voucher_data = self.miracle_api_call(endpoint, method, payload)
    #     resPartner = self.env['res.partner']
    #     resPartner._action_insert_miracle_account(voucher_data)
    #     _logger.info("this is partner data %s", voucher_data)