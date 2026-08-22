from odoo import fields, models
from odoo.tools import html2plaintext
from odoo.exceptions import UserError
from datetime import datetime
import logging
_logger = logging.getLogger(__name__)

class SaleOrder(models.Model):
    _inherit = 'sale.order'

    # miracle_voucher_id = fields.Char(string="Miracle Voucher ID", readonly=True,copy=False)
    miracle_sale_quotation_id = fields.Char(string="Miracle Quotation ID", readonly=True,copy=False)
    miracle_sale_order_id = fields.Char(string="Miracle Order ID", readonly=True,copy=False)
    is_miracle_voucher = fields.Boolean(string="Is Miracle Voucher",readonly=True,copy=False)

    def action_upload_sale_to_miracle(self):
        if self.env.context.get('skip_miracle_sync'):
            return
        self.ensure_one()
        company = self.env.company

        if self.state  in ['draft']:
            current_id = self.miracle_sale_quotation_id
        elif self.state in ['sale']:
            current_id = self.miracle_sale_order_id
        else:
            return company.miracle_notification(
                "Only Quotation or Confirmed Orders can be synced.",
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

        if self.payment_term_id and self.payment_term_id.name == "Immediate Payment":
            flgcd = "C"
        else:
            flgcd = "D"
        
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
                # "seqno": seq,
                "qty1": line.product_uom_qty,
                "txpaidrt": line.tax_id[:1].amount if line.tax_id else 0,
                "rate": line.price_unit,
                "amt": line.price_subtotal,
            }

            items.append(item)
            _logger.info("this is items %s",items)
            # seq += 1

        payload = {
            "action": action_type,
            "acc": self.partner_id.miracle_account_id,
            "billamt": self.amount_total,
            "flgcd": flgcd,
            "narr": html2plaintext(self.note or ""),
            "invtyp": "GST" if self.partner_id.state_id == self.company_id.state_id else "IGST",
            # "taxtyp": "T",
            "items": items
        }

        if self.state in ['draft']:
            payload.update({
                "voutyp": "QS",
                "quotdt": self.date_order and self.date_order.strftime("%Y-%m-%d"),
                "quotno": self.name
            })
        elif self.state in ['sale']:
            payload.update({
                "voutyp": "OS",
                "orddt": self.date_order.strftime("%Y-%m-%d"),
                "ordno": self.name
            })

        if action_type == "E":
            payload['uniqueId'] = current_id

        _logger.info("this is payload %s",payload)

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
            
            if self.state in ['draft']:
                self.with_context(skip_miracle_sync=True).write({
                    "miracle_sale_quotation_id": unique_id,
                    "is_miracle_voucher" : True
                })
            elif self.state in ['sale']:
                self.with_context(skip_miracle_sync=True).write({
                    "miracle_sale_order_id": unique_id,
                    "is_miracle_voucher": True
                })

        return company.miracle_notification(
            request.get("Message"),
            "success"
        )

    def action_sync_sale_from_miracle(self):
        self.ensure_one()
        company = self.env.company

        if self.state in ['draft']:
            miracle_id = self.miracle_sale_quotation_id
        elif self.state in ['sale']:
            miracle_id = self.miracle_sale_order_id
        else:
            return company.miracle_notification(
                "Only Quotation or Confirmed Orders can be synced.",
                "danger"
            )

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
                "Customer not found. Please sync customer first.",
                "danger"
            )

        voucher_type = data.get('voutyp')

        if voucher_type == 'QS':
            order_date = data.get('quotdt')
        elif voucher_type == 'OS':
            order_date = data.get('orddt')
        else:
            return company.miracle_notification(
                "Quotation date or Order date is not found",
                "danger"
            )

        self.write({
            'partner_id': partner.id,
            'date_order': order_date,
            'note': data.get('narr'),
        })

        existing_lines = {
            line.product_id.miracle_product_id: line
            for line in self.order_line
            if line.product_id.miracle_product_id
        }

        miracle_products = []

        for item in data.get('items', []):
            miracle_prd = item.get('prd')
            miracle_products.append(miracle_prd)

            product = self.env['product.product'].search([
                ('miracle_product_id', '=', miracle_prd)
            ], limit=1)

            if not product:
                return company.miracle_notification(
                    f"Product not found for Miracle ID: {miracle_prd}",
                    "danger"
                )

            tax_ids = []
            for exp in item.get('expdet', []):
                tax = self.env['account.tax'].search([
                    ('amount', '=', exp.get('expper')),
                    ('type_tax_use', '=', 'sale')
                ], limit=1)
                if tax:
                    tax_ids.append(tax.id)

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
                    'product_uom_qty': qty1,
                    'price_unit': item.get('rate'),
                    'tax_id': [(6, 0, tax_ids)]
                })

            else:
                self.env['sale.order.line'].create({
                    'order_id': self.id,
                    'product_id': product.id,
                    'name': product.name,
                    'product_uom_qty': qty1,
                    'price_unit': item.get('rate'),
                    'tax_id': [(6, 0, tax_ids)]
                })

        for line in self.order_line:
            if line.product_id.miracle_product_id not in miracle_products:
                line.unlink()

        return company.miracle_notification(
            "Sale synced successfully from Miracle.",
            "success"
        )