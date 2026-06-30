from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    miracle_post_voucher_url = fields.Char(related="company_id.miracle_post_voucher_url", readonly=True)
    miracle_get_voucher_url = fields.Char(related="company_id.miracle_get_voucher_url", readonly=True)