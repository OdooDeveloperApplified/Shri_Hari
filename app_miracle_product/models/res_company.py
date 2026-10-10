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
    

    def _action_get_miracle_stock_ledger(self, miracle_product_ids=None):
        self.ensure_one()
        endpoint = self.miracle_product_ledger_url
        payload = {
            "fromdate": "2026-04-01",
            "todate": "2027-03-31",
            "rptfield": ["prdid", "opqty1", "recqty1", "iqty1", "clqty1", "clqty2"],
            "rptfilter": {}
        }
        if miracle_product_ids:
            payload["rptfilter"]["prdid"] = miracle_product_ids

        stock_data = self.miracle_api_call(endpoint, "post", payload, trigger_label="Stock Ledger Sync")
        return self.env['product.template'].with_company(self)._sync_stock_from_ledger(stock_data)

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
                "recqty1",
                "iqty1",
                "clqty1",
                # "uomnm", #if they give we will uncomment it
                # "opqty2",
                # "recqty2",
                # "iqty2",
                "clqty2",
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
 
        product_data = self.miracle_api_call(endpoint, method, payload, trigger_label="Product Ledger Full Sync")
        productTemplate = self.env['product.template']
        _logger.info("this is product data %s", product_data)
        return productTemplate._action_insert_miracle_product(product_data)

    def _action_send_product_to_miracle(self, payload, trigger_label=None, reference=None, res_model=None, res_id=None):
        self.ensure_one()
        request = self.miracle_api_call(self.miracle_post_product_url,"post",payload, trigger_label=trigger_label, reference=reference, res_model=res_model, res_id=res_id)
        return request

    def _action_get_product_from_miracle(self, payload, trigger_label=None, reference=None, res_model=None, res_id=None):
        self.ensure_one()
        response = self.miracle_api_call(self.miracle_get_product_url,"get",payload, trigger_label=trigger_label, reference=reference, res_model=res_model, res_id=res_id)
        return response
        
