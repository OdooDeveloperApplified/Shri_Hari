from odoo import api, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.model_create_multi
    def create(self, vals_list):
        orders = super().create(vals_list)
        orders._add_mobile_freight_charge()
        return orders

    def _add_mobile_freight_charge(self):
        """Add a Freight & Transport Charges line, priced at the freight
        product's Sales Price per unit of everything else on the order.
        Runs on every sale.order creation, regardless of whether the order
        came from the mobile app or was created directly in Odoo, so both
        sides stay in sync automatically.
        """
        for order in self:
            freight_product = order.company_id.mobile_freight_product_id
            if not freight_product:
                continue

            freight_variant = freight_product.product_variant_id
            if freight_variant in order.order_line.product_id:
                # Already has a freight line (e.g. duplicated via copy()).
                continue

            billable_lines = order.order_line.filtered(
                lambda line: line.product_id and line.product_id != freight_variant
            )
            total_qty = sum(billable_lines.mapped('product_uom_qty'))
            if not total_qty:
                continue

            order.order_line.create({
                'order_id': order.id,
                'product_id': freight_variant.id,
                'product_uom_qty': total_qty,
                'price_unit': freight_product.list_price,
            })
