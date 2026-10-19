from odoo import models, fields


class ProductCategory(models.Model):
    _name = 'product.category'
    _inherit = ['product.category', 'image.mixin']

    show_in_mobile_app = fields.Boolean(
        string="Show in Mobile App",
        default=True,
        help="If checked, this category and its products will be visible in the mobile application. Untick to hide."
    )
