from odoo import models


class ProductCategory(models.Model):
    _name = 'product.category'
    _inherit = ['product.category', 'image.mixin']
