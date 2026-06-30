from odoo import models, fields
from datetime import timedelta
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = "res.company"

    miracle_product_ledger_url = fields.Char("Product Ledger URL", default="TPA/M2/V1/ProductLedger", readonly=True)
    miracle_get_product_url = fields.Char("Get Product URL", default="TPA/M2/V1/GetProduct", readonly=True)
    miracle_post_product_url = fields.Char("Product Create URL", default="TPA/M2/V1/Product", readonly=True)
    

    def _action_get_miracle_product_ledger(self):
        _logger.info("Starting to fetch product ledger from Miracle")
        endpoint = self.miracle_product_ledger_url
        method="post"
        payload = {
            "fromdate": "2026-04-01",
            "todate": "2027-03-31",
            "rptfield": [
                "prdnm",
                "prdid",
                # "prdaliam",
                "grpnm",
                # "grpaliam",
                "catnm",
                # "catalim",
                "gstunt",
                "hsncode",
                "minstk",
                "ordlev",
                "lprate",
                "lsrate",
                "prdmrp",
                "commnm",
                # "prdtype",
                "slabnm",
                "opamt",
                "opqty1",
                "recqty1",
                "iqty1",
                "clqty1",
                # "opqty2",
                # "recqty2",
                # "iqty2",
                # "clqty2",
                # "opqty3",
                # "recqty3",
                # "iqty3",
                # "clqty3",
                # "opqty4",
                # "recqty4",
                # "iqty4",
                # "clqty4",
                # "opqty5",
                # "recqty5",
                # "iqty5",
                # "clqty5"
            ],
            "rptfilter": {}
        }
 
        product_data = self.miracle_api_call(endpoint, method, payload)
        productTemplate = self.env['product.template']
        _logger.info("this is product data %s", product_data)
        return productTemplate._action_insert_miracle_product(product_data)

    def _action_send_product_to_miracle(self,payload):
        self.ensure_one()
        request = self.miracle_api_call(self.miracle_post_product_url,"post",payload)
        return request

    def _action_get_product_from_miracle(self,payload):
        self.ensure_one()
        response = self.miracle_api_call(self.miracle_get_product_url,"get",payload)
        return response
        