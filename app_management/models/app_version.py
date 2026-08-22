from odoo import models, fields, api
from odoo.exceptions import ValidationError


class AppVersion(models.Model):
    _name = 'app.version'
    _description = 'App Version'
    _rec_name = 'android_version'

    android_version = fields.Char(string='Android Version', required=True)
    ios_version = fields.Char(string='iOS Version', required=True)

    @api.model
    def create(self, vals):
        if self.search_count([]) >= 1:
            raise ValidationError("Only one record is allowed in App Management.")
        return super().create(vals)