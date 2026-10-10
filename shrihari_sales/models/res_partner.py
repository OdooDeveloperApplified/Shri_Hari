from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    email = fields.Char(required=False)

    apply_freight_charge = fields.Boolean(
        string="Apply Freight & Transport Charge",
        default=False,
        help="If checked, the Mobile App Freight & Transport charge will be auto-added to this customer's orders."
    )
