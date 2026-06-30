from odoo import fields, models
from odoo.exceptions import UserError
import requests
import logging
_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    miracle_product_ledger_url = fields.Char(related="company_id.miracle_product_ledger_url",readonly=True)
    miracle_get_product_url = fields.Char(related="company_id.miracle_get_product_url", readonly=True)
    miracle_post_product_url = fields.Char(related="company_id.miracle_post_product_url", readonly=True)

    def action_get_miracle_product_ledger(self):
        company = self.company_id
        return company._action_get_miracle_product_ledger()