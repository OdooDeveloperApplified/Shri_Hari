from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    whatsapp_api_domain = fields.Char(related="company_id.whatsapp_api_domain", readonly=False)
    whatsapp_api_version = fields.Char(related="company_id.whatsapp_api_version", readonly=False)
    whatsapp_phone_number_id = fields.Char(related="company_id.whatsapp_phone_number_id", readonly=False)
    whatsapp_access_token = fields.Char(related="company_id.whatsapp_access_token", readonly=False)
    whatsapp_otp_template_name = fields.Char(related="company_id.whatsapp_otp_template_name", readonly=False)
    whatsapp_otp_template_lang = fields.Char(related="company_id.whatsapp_otp_template_lang", readonly=False)
    whatsapp_otp_test_mobile = fields.Char(related="company_id.whatsapp_otp_test_mobile", readonly=False)
    whatsapp_otp_test_code = fields.Char(related="company_id.whatsapp_otp_test_code", readonly=False)
