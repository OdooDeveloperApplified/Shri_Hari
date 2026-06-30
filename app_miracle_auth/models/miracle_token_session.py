# -*- coding: utf-8 -*-
from odoo import models, fields, api


class MiracleTokenSession(models.Model):
    _name = "miracle.token.session"
    _description = "Miracle Token Session"
    _order = "generated_at desc"

    company_id = fields.Many2one("res.company", required=True, ondelete="cascade")

    token = fields.Char("Token", required=True)

    generated_at = fields.Datetime("Generated At", required=True)
    expiry_at = fields.Datetime("Expiry At", required=True)

    state = fields.Selection([
        ("active", "Active"),
        ("expired", "Expired"),
    ], default="active")

    api_call_ids = fields.One2many(
        "miracle.api.log",
        "session_id",
        string="API Calls",
    )

    api_call_count = fields.Integer(
        compute="_compute_api_call_count",
        string="API Call Count",
    )

    @api.depends("api_call_ids")
    def _compute_api_call_count(self):
        for rec in self:
            rec.api_call_count = len(rec.api_call_ids)

    def action_mark_expired(self):
        self.write({"state": "expired"})