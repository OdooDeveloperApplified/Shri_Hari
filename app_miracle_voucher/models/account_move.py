from odoo import fields, models
from odoo.tools import html2plaintext
import logging
_logger = logging.getLogger(__name__)

class AccountMove(models.Model):
    _inherit = 'account.move'

    miracle_voucher_id = fields.Char(string="Miracle Voucher ID", readonly=True,copy=False)
    is_miracle_voucher = fields.Boolean(string="Is Miracle Voucher",readonly=True,copy=False)
    miracle_reason_id = fields.Many2one('miracle.reason',string="CN/DN Reason")

    def action_upload_invoice_to_miracle(self):
        if self.env.context.get('skip_miracle_sync'):
            return
        self.ensure_one()
        company = self.env.company

        EFFECT_MAPPING = {
            "out_invoice": "Increase Sales",
            "in_invoice": "Increase Purchase",
            "out_refund": "Decrease Sales",
            "in_refund": "Decrease Purchase",
        }
        
        effect_value = EFFECT_MAPPING.get(self.move_type)

        if self.move_type not in ['out_invoice','in_invoice','in_refund','out_refund']:
            return company.miracle_notification(
                "Only Customer Invoice or Vendor Bill can be exported to Miracle",
                "danger"
            )

        if self.miracle_voucher_id:
            action_type = "E"
        else:
            action_type = "A"

        if not self.partner_id.miracle_account_id:
            return company.miracle_notification(
                "Partner not synced with Miracle",
                "danger"
            )

        with_stock_items = []
        without_stock_items = []

        for line in self.invoice_line_ids:
            if line.product_id:
                if not line.product_id.miracle_product_id:
                    return company.miracle_notification(
                        f"Product {line.product_id.name} not synced with Miracle",
                        "danger"
                    )

                item = {
                    "prd": line.product_id.miracle_product_id,
                    "qty1": line.quantity,
                    "txpaidrt": line.tax_ids and line.tax_ids[0].amount or 0,
                    "rate": line.price_unit,
                    "amt": line.price_subtotal,
                }
                with_stock_items.append(item)

            else:
                if not line.account_id:
                    continue
            
                if not line.account_id.miracle_account_id:
                    return company.miracle_notification(
                        f"Account {line.account_id.name} not synced with Miracle",
                        "danger"
                    )

                item = {
                    "itemacc": line.account_id.miracle_account_id,
                    "assamt": line.price_subtotal,
                    "gstper": line.tax_ids and line.tax_ids[0].amount or 0
                }
                without_stock_items.append(item)
        
        reason_value = False
        has_product = any(line.product_id for line in self.invoice_line_ids)

        if self.move_type in ['out_refund','in_refund'] and not has_product:
            if not self.miracle_reason_id:
                return company.miracle_notification(
                    "Please select CN/DN Reason",
                    "danger"
                )
            
            reason_value = f"{str(self.miracle_reason_id.code).zfill(2)}-{self.miracle_reason_id.name}"


        payload = {
            "action": action_type,
            "acc": self.partner_id.miracle_account_id,
            # "billamt": self.amount_total,
            "flgcd": "D",
            "narr": html2plaintext(self.narration or ""),
            # "invtyp": "GST (SRet.)",
            "taxtyp": "T",
        }

        if self.move_type == "out_invoice":
            payload.update({
                "voutyp": "SS",
                "billdt": self.invoice_date.strftime("%Y-%m-%d"),
                "billno": self.name,
                "billamt": self.amount_total,
                "invtyp": "GST" if self.partner_id.state_id == self.company_id.state_id else "IGST",
                "items": with_stock_items
            })

        elif self.move_type == "in_invoice":
            payload.update({
                "voutyp": "PP",
                "voudt": self.invoice_date.strftime("%Y-%m-%d"),
                "vouno": self.name,
                "billamt": self.amount_total,
                "invtyp": "GST" if self.partner_id.state_id == self.company_id.state_id else "IGST",
                "items": with_stock_items
            })
            
        elif self.move_type == "out_refund":
            original_invoice = self.reversed_entry_id
            has_product = any(line.product_id for line in self.invoice_line_ids)

            if not has_product:
                payload.update({
                    "voutyp": "N6",
                    "voudt": self.invoice_date.strftime("%Y-%m-%d"),
                    "vouno": self.name,
                    # "billamt": self.amount_total,
                    "invtyp": "GST (SRet.)",
                    "cndneff": effect_value,
                    "reason": reason_value,
                    "wositems": without_stock_items
                })
            else:
                if not original_invoice:
                    return company.miracle_notification(
                        "Original invoice not found for Sales Return",
                        "danger"
                    )

                payload.update({
                    "voutyp": "SR",
                    "billdt": self.invoice_date.strftime("%Y-%m-%d"),
                    "billno": self.name,
                    "billamt": self.amount_total,
                    "orgbilldt": original_invoice.invoice_date.strftime("%Y-%m-%d"),
                    "orgbillno": original_invoice.name,
                    "invtyp": "GST" if self.partner_id.state_id == self.company_id.state_id else "IGST",
                    "items": with_stock_items
                })

        elif self.move_type == "in_refund":
            original_bill = self.reversed_entry_id
            has_product = any(line.product_id for line in self.invoice_line_ids)

            if not has_product:
                payload.update({
                    "voutyp": "N7",
                    "voudt": self.invoice_date.strftime("%Y-%m-%d"),
                    "vouno": self.name,
                    # "billamt": self.amount_total,
                    "invtyp": "GST (PRet.)",
                    "cndneff": effect_value,
                    "reason": reason_value,
                    "wositems": without_stock_items
                })
            else:
                if not original_bill:
                    return company.miracle_notification(
                        "Original bill not found for purchase",
                        "danger"
                    )

                payload.update({
                    "voutyp": "PR",
                    "voudt": self.invoice_date.strftime("%Y-%m-%d"),
                    "vouno": self.name,
                    "billamt": self.amount_total,
                    "orgbilldt": original_bill.invoice_date.strftime("%Y-%m-%d"),
                    "orgbillno": original_bill.name,
                    "invtyp": "GST",
                    "items": with_stock_items
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

    def action_sync_invoice_from_miracle(self):
        self.ensure_one()
        company = self.env.company

        if not self.miracle_voucher_id:
            return company.miracle_notification(
                "No Miracle voucher ID found to sync.",
                "danger"
            )

        payload = {
            'id': self.miracle_voucher_id
        }

        response = company._action_get_voucher_from_miracle(payload)

        if response.get('IsError'):
            return company.miracle_notification(
                response.get('Message'),
                "danger"
            )

        data = response.get('DataModel')
        if not data:
            return company.miracle_notification(
                "Voucher not found in Miracle."
                "danger"
            )

        voutyp = data.get('voutyp')
        TYPE_MAPPING = {
            'SS': 'out_invoice',
            'PP': 'in_invoice'
        }

        move_type = TYPE_MAPPING.get(voutyp)

        if not move_type:
            return company.miracle_notification(
                f"Unsupported voucher type: {voutyp}",
                "danger"
            )

        if self.move_type != move_type:
            return company.miracle_notification(
                f"Mismatch: Miracle is {voutyp} but Odoo is {self.move_type}",
                "danger"
            )

        partner = self.env['res.partner'].search([
            ('miracle_account_id','=',data.get('acc'))
        ],limit=1)

        if not partner:
            return company.miracle_notification(
                "Partner not found. Please sync Partner first.",
                "danger"
            )

        vals = {
            'partner_id': partner.id,
            'narration': data.get('narr'),
        }

        if move_type == 'out_invoice':
            vals.update({
                'invoice_date': data.get('billdt'),
            })

        elif move_type == 'in_invoice':
            vals.update({
                'invoice_date': data.get('voudt'),
                'ref': data.get('vouno'),
            })

        self.write(vals)

        tax_type = 'sale' if move_type == 'out_invoice' else 'purchase'

        for item in data.get('items', []):
            miracle_prd = item.get('prd')

            product = self.env['product.product'].search([
                ('miracle_product_id', '=', miracle_prd)
            ], limit=1)

            if not product:
                return company.miracle_notification(
                    f"Product not found for Miracle ID: {miracle_prd}",
                    "danger"
                )

            tax_ids = []
            tax_rate = item.get('txpaidrt', 0)

            if tax_rate:
                tax = self.env['account.tax'].search([
                    ('amount', '=', tax_rate),
                    ('type_tax_use', '=', tax_type)
                ], limit=1)

                if tax:
                    tax_ids.append(tax.id)

            self.env['account.move.line'].create({
                'move_id': self.id,
                'product_id': product.id,
                'name': product.name,
                'quantity': item.get('qty1'),
                'price_unit': item.get('rate'),
                'tax_ids': [(6, 0, tax_ids)],
            })

        return company.miracle_notification(
            response.get('Message'),
            "success"
        )