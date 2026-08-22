from odoo import fields, models

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    mobile_app_pricelist_id = fields.Many2one(
        related='company_id.mobile_app_pricelist_id',
        readonly=False,
        string="Mobile App Global Pricelist"
    )
