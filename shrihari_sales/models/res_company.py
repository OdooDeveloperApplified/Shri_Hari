from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    mobile_app_pricelist_id = fields.Many2one('product.pricelist', string="Mobile App Global Pricelist")
