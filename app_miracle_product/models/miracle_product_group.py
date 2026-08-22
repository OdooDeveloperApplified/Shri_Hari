from odoo import models, fields

class MiracleProductGroup(models.Model):
    _name = "miracle.product.group"
    _description = "Miracle Product Group"

    name = fields.Char("Group Name", required=True)
