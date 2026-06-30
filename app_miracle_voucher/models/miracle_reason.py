from odoo import fields, models

class MiracleReasons(models.Model):
    _name = 'miracle.reason'
    _description = "Master for Miracle Reasons"

    name = fields.Char(string="Reason Label",required=True)
    code = fields.Integer(string="Reason Code",required=True)
    active = fields.Boolean(default=True)