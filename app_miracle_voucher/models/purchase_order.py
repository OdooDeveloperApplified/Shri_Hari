from odoo import fields, models
from odoo.tools import html2plaintext
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    # miracle_voucher_id = fields.Char(string="Miracle Voucher ID", readonly=True,copy=False)
    miracle_purchase_quotation_id = fields.Char(string="Miracle Quotation ID", readonly=True, copy=False)
    miracle_purchase_order_id = fields.Char(string="Miracle Order ID", readonly=True, copy=False)
    is_miracle_voucher = fields.Boolean(string="Is Miracle Voucher", readonly=True,copy=False)

    def action_upload_purchase_to_miracle(self):
        self.ensure_one()
        company = self.env.company

        if self.state in ['draft']:
            current_id = self.miracle_purchase_quotation_id
        elif self.state in ['purchase']:
            current_id = self.miracle_purchase_order_id
        else:
            return company.miracle_notification(
                "Only RFQ or Confirmed Purchase Orders can be synced.",
                "danger"
            )

        if current_id:
            action_type = "E"         
        else:
            action_type = "A"
        
        if not self.partner_id.miracle_account_id:
            return company.miracle_notification(
                "Partner is not Synced with Miracle",
                "danger"
            )

        items = []
        # seq = 1
        
        for line in self.order_line:
            if not line.product_id:
                continue
            if not line.product_id.miracle_product_id:
                return company.miracle_notification(
                    f"Product {line.product_id.name} not synced with Miracle",
                    "danger"
                )

            item = {
                "prd": line.product_id.miracle_product_id,
                "qty1": line.product_uom_qty,
                "txpaidrt": line.taxes_id[:1].amount if line.taxes_id else 0,
                "rate": line.price_unit,
                "amt": line.price_subtotal,
            }

            items.append(item)
            # seq += 1

        payload = {
            "action": action_type,
            "acc": self.partner_id.miracle_account_id,
            "billamt": self.amount_total,
            "flgcd": "D",
            "narr": html2plaintext(self.notes or ""),
            "invtyp": "GST" if self.partner_id.state_id == self.company_id.state_id else "IGST",
            # "taxtyp": "T",
            "items": items
        }

        if self.state in ['draft']:
            payload.update({
                "voutyp": "QP",
                "quotdt": self.date_order.strftime("%Y-%m-%d"),
                "quotno": self.name
            })
        elif self.state in ['purchase']:
            payload.update({
                "voutyp": "OP",
                "orddt": self.date_order.strftime("%Y-%m-%d"),
                "ordno": self.name
            })

        if action_type == "E":
            payload['uniqueId'] = current_id

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
                "miracle_purchase_order_id": unique_id,
                "is_miracle_voucher": True
            })

        return company.miracle_notification(
            request.get("Message"),
            "success"
        )

    def action_sync_purchase_from_miracle(self):
        self.ensure_one()
        company = self.env.company

        # Simply use the single ID for everything (now acting as Challan/Order ID)
        miracle_id = self.miracle_purchase_order_id
        if not miracle_id:
            return company.miracle_notification(
                "No Miracle ID found to sync.",
                "danger"
            )

        payload = {
            "id": miracle_id
        }

        response = company._action_get_voucher_from_miracle(payload)

        if response.get("IsError"):
            return company.miracle_notification(
                response.get("Message"),
                "danger"
            )

        data = response.get("DataModel")
        if not data:
            return company.miracle_notification(
                "Voucher not found in Miracle.",
                "danger"
            )

        partner = self.env['res.partner'].search([
            ('miracle_account_id', '=', data.get('acc'))
        ], limit=1)

        if not partner:
            return company.miracle_notification(
                "Vendor not found. Please sync vendor first.",
                "danger"
            )

        voucher_type = data.get('voutyp')

        if voucher_type == 'QP':
            order_date = data.get('quotdt')
        elif voucher_type == 'OP':
            order_date = data.get('orddt')
        elif voucher_type == 'HP':
            order_date = data.get('voudt')
        else:
            return company.miracle_notification(
                "RFQ date, Order date or Voucher date is not found",
                "danger"
            )

        self.write({
            'partner_id': partner.id,
            'date_order': order_date,
            'notes': data.get('narr'),
        })

        existing_lines = {
            line.product_id.miracle_product_id: line
            for line in self.order_line
            if line.product_id.miracle_product_id
        }

        miracle_products = []

        for item in data.get('items',[]):
            miracle_prd = item.get('prd')
            miracle_products.append(miracle_prd)

            product = self.env['product.product'].search([
                ('miracle_product_id', '=', miracle_prd)
            ], limit=1)

            if not product:
                return company.miracle_notification(
                    f"Product not found for ID {miracle_prd}",
                    "danger"
                )

            qty1 = item.get('qty1') or 0.0
            uom = product.uom_id
            if uom:
                if uom.uom_type == 'bigger':
                    qty1 = qty1 / uom.factor_inv
                elif uom.uom_type == 'smaller' and uom.factor > 0:
                    qty1 = qty1 * uom.factor

            existing_line = existing_lines.get(miracle_prd)

            if existing_line:
                existing_line.write({
                    'product_qty': qty1,
                    'price_unit': item.get('rate'),
                })
            else:
                self.env['purchase.order.line'].create({
                    'order_id': self.id,
                    'product_id': product.id,
                    'name': product.name,
                    'product_qty': qty1,
                    'price_unit': item.get('rate'),
                })

        for line in self.order_line:
            if line.product_id.miracle_product_id not in miracle_products:
                line.unlink()

        return company.miracle_notification(
            "Purchase Order synced successfully.",
            "success"
        )