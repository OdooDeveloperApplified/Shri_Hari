from odoo import fields, models
import requests
import logging

_logger = logging.getLogger(__name__)


class ResCompany(models.Model):
    _inherit = "res.company"

    # Mobile app proxy endpoints (shrihari_api) - the app no longer calls
    # Miracle directly for these; Odoo calls Miracle on its behalf. Stored
    # as fields, same convention as app_miracle_product/app_miracle_account/
    # app_miracle_voucher, so a path never needs a code change if Miracle
    # ever revises it.
    miracle_account_balance_url = fields.Char("Account Balance URL", default="TPA/M2/V1/AccountBalance", readonly=True)
    miracle_account_voucher_list_url = fields.Char("Account Voucher List URL", default="TPA/M2/V1/AccountVoucherList", readonly=True)
    miracle_generate_file_url = fields.Char("Generate File URL", default="TPA/M2/V1/GenerateFile", readonly=True)

    # WhatsApp OTP login - config for the Meta-format send endpoint:
    # {whatsapp_api_domain}/api/meta/{whatsapp_api_version}/{whatsapp_phone_number_id}/messages
    whatsapp_api_domain = fields.Char("WhatsApp API Domain")
    whatsapp_api_version = fields.Char("WhatsApp API Version")
    whatsapp_phone_number_id = fields.Char("WhatsApp Phone Number ID")
    whatsapp_access_token = fields.Char("WhatsApp Access Token")
    whatsapp_otp_template_name = fields.Char("WhatsApp OTP Template Name", default="shreehari_otp")
    whatsapp_otp_template_lang = fields.Char("WhatsApp OTP Template Language", default="en")

    # Store review bypass: Google Play / Apple App Store reviewers log in
    # with this exact mobile number and always get this fixed code, with no
    # real WhatsApp message ever sent - reviewers have no way to receive
    # one. Leave both blank to disable the bypass entirely.
    whatsapp_otp_test_mobile = fields.Char("Store Review Test Mobile")
    whatsapp_otp_test_code = fields.Char("Store Review Static OTP")

    def _send_whatsapp_otp(self, mobile, otp_code):
        """Send `otp_code` to `mobile` via the approved WhatsApp
        Authentication template (has a Copy Code button, so the same code
        goes in both the body and the button parameter).
        """
        self.ensure_one()

        # whatsapp_api_domain is expected to already include the vendor's
        # own base path (e.g. "https://crm.ihakimi.com/api/meta", exactly
        # as their dashboard labels it "API URL") - only the version and
        # phone number id get appended here.
        url = "%s/%s/%s/messages" % (
            self.whatsapp_api_domain.rstrip("/"),
            self.whatsapp_api_version,
            self.whatsapp_phone_number_id,
        )

        payload = {
            "messaging_product": "whatsapp",
            "to": mobile,
            "recipient_type": "individual",
            "type": "template",
            "template": {
                "language": {"policy": "deterministic", "code": self.whatsapp_otp_template_lang},
                "name": self.whatsapp_otp_template_name,
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": otp_code}]
                    },
                    {
                        "type": "button",
                        "sub_type": "url",
                        "index": 0,
                        "parameters": [{"type": "text", "text": otp_code}]
                    }
                ]
            }
        }

        headers = {
            "Authorization": "Bearer %s" % self.whatsapp_access_token,
            "Content-Type": "application/json",
        }

        # verify=False: same precedent already in use for Miracle's own
        # miracle_api_call() - this vendor's TLS cert doesn't validate
        # against its own hostname either.
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        try:
            data = response.json()
        except Exception:
            data = response.text

        if response.ok:
            _logger.info("WhatsApp OTP sent to %s: %s", mobile, data)
        else:
            _logger.error("WhatsApp OTP send to %s failed (%s): %s", mobile, response.status_code, data)

        response.raise_for_status()
        return data
