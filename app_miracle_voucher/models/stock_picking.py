from odoo import fields, models
import logging
_logger = logging.getLogger(__name__)

class StockPicking(models.Model):
    _inherit = 'stock.picking'

    miracle_voucher_id = fields.Char(string="Miracle Voucher ID",readonly=True, copy=False)
    is_miracle_voucher = fields.Boolean(string="Is Miracle Voucher", readonly=True, copy=False)

    def action_upload_challan_to_miracle(self):
        if self.env.context.get('skip_miracle_sync'):
            return
        self.ensure_one()
        company = self.env.company

        if self.miracle_voucher_id:
            action_type = "E"
        else:
            action_type = "A"

        if not self.partner_id.miracle_account_id:
            return company.miracle_notification(
                "Partner not synced with Miracle",
                "danger"
            )
        
        items = []
        order = False

        for seq, move in enumerate(self.move_ids_without_package, start=1):

            if not move.product_id:
                continue

            if not move.product_id.miracle_product_id:
                return company.miracle_notification(
                    f"Product {move.product_id.display_name} not synced with Miracle",
                    "danger"
                )

            qty = move.product_uom_qty
            # qty = sum(move.move_line_ids.mapped('quantity'))

            if self.picking_type_id.code == "incoming":
                po_line = move.purchase_line_id
                rate = po_line.price_unit if po_line else 0
                order = po_line.order_id if po_line else order

            elif self.picking_type_id.code == "outgoing":
                so_line = move.sale_line_id
                rate = so_line.price_unit if so_line else 0
                order = so_line.order_id if so_line else order

            else:
                rate = 0

            amount = qty * rate

            # _logger.info("Product: %s | Qty: %s | Rate: %s", move.product_id.display_name, qty, rate)

            lot_lines = move.move_line_ids.filtered(lambda ml: ml.lot_id)

            for ml in lot_lines:
                _logger.info("Product=%s | Lot=%s | Qty=%s",move.product_id.display_name,ml.lot_id.name,ml.quantity)

            # ==========================
            # MULTI LOT SUPPORT
            # ==========================
            if lot_lines:
                for ml in lot_lines:
                    items.append({
                        "prd": move.product_id.miracle_product_id,
                        "seqno": len(items) + 1,
                        "qty1": ml.quantity,
                        "txpaidrt": 0,
                        "rate": rate,
                        "amt": ml.quantity * rate,
                        "batchnm": ml.lot_id.name,
                    })
            else:
                items.append({
                    "prd": move.product_id.miracle_product_id,
                    "seqno": len(items) + 1,
                    "qty1": qty,
                    "txpaidrt": 0,
                    "rate": rate,
                    "amt": amount,
                })

            # lot_name = ""
            # move_line = move.move_line_ids.filtered(lambda ml: ml.lot_id)[:1]
            # _logger.info("this is move_line %s",move_line)

            # if move_line:
            #     lot_name = move_line.lot_id.name
            #     _logger.info("this is lot_name %s",lot_name)

            # item_vals = {
            #     "prd": move.product_id.miracle_product_id,
            #     "seqno": seq,
            #     "qty1": qty,
            #     "txpaidrt": 0,
            #     "rate": rate,
            #     "amt": amount,
            # }

            # if lot_name:
            #     item_vals["batchnm"] = lot_name

            # items.append(item_vals)

        if not order:
            return company.miracle_notification(
                f"Source order not found for picking {self.name}",
                "danger"
            )

        payload = {
            "action": action_type,
            "acc": self.partner_id.miracle_account_id,
            "billamt": order.amount_total,
            "flgcd": "D",
            "invtyp": "GST" if self.partner_id.state_id == self.company_id.state_id else "IGST",
            "taxtyp": "T",
            "items": items
        }

        if self.picking_type_id.code == "outgoing":
            payload.update({
                "voutyp": "HS",
                "chno": self.name,
                "chdt": self.date_done.strftime("%Y-%m-%d"),
            })

        elif self.picking_type_id.code == "incoming":
            payload.update({
                "voutyp": "HP",
                "voudt": order.date_order.strftime("%Y-%m-%d"),
                "vouno": order.name,
                "chno": self.name,
                "chdt": self.date_done.strftime("%Y-%m-%d"),
            })

        else:
            return company.miracle_notification(
                "Unsupported picking type",
                "danger"
            )

        if action_type == "E":
            payload['uniqueId'] = self.miracle_voucher_id

        _logger.info("MIRACLE PAYLOAD = %s", payload)
        response = company._action_send_voucher_to_miracle(payload)

        if response.get("IsError"):
            return company.miracle_notification(
                response.get("Message"),
                "danger"
            )

        if action_type == "A":
            unique_id = response.get("UniqueId")

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
            response.get("Message"),
            "success"
        )