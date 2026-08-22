# -*- coding: utf-8 -*-

from odoo import models, api

class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def _get_login_domain(self, login):
        return ['|', ('login', '=', login), ('mobile', '=', login)]
