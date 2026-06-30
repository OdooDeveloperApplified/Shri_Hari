from odoo import fields, models
from odoo.exceptions import UserError
import requests
import logging
_logger = logging.getLogger(__name__)


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    miracle_account_ledger_url = fields.Char(related="company_id.miracle_account_ledger_url",readonly=True)
    miracle_get_account_url = fields.Char(related="company_id.miracle_get_account_url", readonly=True)
    miracle_post_account_url = fields.Char(related="company_id.miracle_post_account_url", readonly=True)

    def action_get_miracle_account_ledger(self):
        company = self.company_id
        return company._action_get_miracle_account_ledger()

    def action_get_miracle_account(self):
        company = self.company_id
        company._action_get_miracle_account()