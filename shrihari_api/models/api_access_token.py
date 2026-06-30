from odoo import models, fields, api
from odoo import http

class PartnerApiKey(models.Model):
    _name = 'partner.api.key'
    _description = 'Partner API Key'

    user_id = fields.Many2one('res.users', string='User', required=True)
    api_key = fields.Char(string='API Key', readonly=True)
    expiry_date = fields.Datetime(string='Expiry Date', readonly=True)

class ResUsers(models.Model):
    _inherit = 'res.users'

    device_token = fields.Char(string="Device Token")

