from odoo import fields, models
from odoo.tools import html2plaintext
import logging
_logger = logging.getLogger(__name__)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    miracle_voucher_id = fields.Char(string="Miracle Voucher ID",readonly=True,copy=False)
    is_miracle_voucher = fields.Boolean(string="Is Miracle Voucher",readonly=True,copy=False)

    def action_send_payment_to_miralce(self):
        self.ensure_one()
        company = self.env.company

        if self.miracle_voucher_id:
            action_type = "E"
        else:
            action_type = "A"

        if not self.partner_id.miracle_account_id:
            return company.miracle_notification(
                "Partner is not Synced with Miracle",
            )

        if not self.journal_id or not self.journal_id.default_account_id.miracle_account_id:
            return company.miracle_notification(
                "Journal (Cash/Bank) is not synced with Miracle",
                "danger"
            )

        if self.payment_type == 'outbound':
            if self.journal_id.type == 'bank':
                voutyp = "BP"
            else:
                voutyp = "CP"
        else:
            if self.journal_id.type == 'bank':
                voutyp = "BR"
            else:
                voutyp = "CR"

        payload = {
            "action": action_type,
            "voutyp": voutyp,
            "voudt": self.date.strftime("%Y-%m-%d"),
            "vouno": self.name,
            "acc": self.partner_id.miracle_account_id,
            "oppacc": self.journal_id.default_account_id.miracle_account_id,
            "amount": self.amount,
            "taxtyp": "O",
            # "narr": html2plaintext(self.bank_reference or ""),
        }

        if self.journal_id.type == 'bank':
            # cheque_date = self.cheque_date or self.date
            payload.update({
                "cheqdt": self.date.strftime("%Y-%m-%d"),
                "cheqno": self.cheque_reference,
            })

        if action_type == "E":
            payload["uniqueId"] = self.miracle_voucher_id

        request = company._action_send_voucher_to_miracle(payload)

        if request.get("IsError"):
            return company.miracle_notification(
                request.get("Message"),
                "danger"
            )

        if action_type == "A":
            unique_id = request.get("UniqueId")

            if not unique_id:
                return company.miracle_notification(
                    "Miracle did not return UniqueId",
                    "danger"
                )

            self.write({
                "miracle_voucher_id": unique_id,
                "is_miracle_voucher": True
            })

        return company.miracle_notification(
            request.get("Message"),
            "success"
        )