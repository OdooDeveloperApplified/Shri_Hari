from odoo import fields, models

class ResCompany(models.Model):
    _inherit = 'res.company'

    mobile_app_pricelist_id = fields.Many2one('product.pricelist', string="Mobile App Global Pricelist")
    mobile_freight_product_id = fields.Many2one(
        'product.template',
        string="Mobile App Freight & Transport Charge Product",
        help="Added as an extra line on every sale order placed from the mobile app. "
             "Quantity = number of product lines in the order, price = this product's Sales Price."
    )
