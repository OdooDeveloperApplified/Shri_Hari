# -*- coding: utf-8 -*-
from odoo import models, fields


class MiracleApiLog(models.Model):
    _name = "miracle.api.log"
    _description = "Miracle API Call Log"
    _order = "create_date desc"

    session_id = fields.Many2one(
        "miracle.token.session",
        required=True,
        ondelete="cascade",
    )

    company_id = fields.Many2one("res.company", required=True)

    name = fields.Char("Endpoint")

    request_url = fields.Char("Request URL")
    request_method = fields.Selection([
        ("get", "GET"),
        ("post", "POST"),
        ("put", "PUT"),
        ("delete", "DELETE"),
    ])

    request_payload = fields.Text("Request Payload")
    response_payload = fields.Text("Response")
    response_code = fields.Integer("HTTP Status")

    status = fields.Selection([
        ("success", "Success"),
        ("failed", "Failed"),
    ])