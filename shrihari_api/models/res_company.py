from odoo import fields, models


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
