from odoo import api, fields, models


class ProductPricelistItem(models.Model):
    _inherit = 'product.pricelist.item'

    mobile_box_price = fields.Float(
        string="Mobile App Box Price",
        compute="_compute_mobile_box_price",
        help="Preview of the actual box price a mobile-app (or backend) "
             "order will be charged once this rule's per-piece rate / MRP "
             "discount is converted using the product's pack size. Not "
             "stored - always reflects the product's current data, so it "
             "can never go stale like a saved value could."
    )

    @api.depends('compute_price', 'fixed_price', 'percent_price',
                 'product_id', 'product_tmpl_id', 'pricelist_id')
    def _compute_mobile_box_price(self):
        for item in self:
            product = item.product_id or item.product_tmpl_id
            company = item.pricelist_id.company_id or item.env.company

            if not product or not item.pricelist_id or item.pricelist_id.id != company.mobile_app_pricelist_id.id:
                item.mobile_box_price = 0.0
                continue

            item.mobile_box_price = item._get_mobile_box_price(product, product.list_price)

    def _get_mobile_box_price(self, product, fallback_price):
        """Box price for `product` under this rule, using the mobile app's
        per-piece pricing convention (Fixed Price = per piece, Discount =
        off Miracle MRP). Returns `fallback_price` unchanged for any rule
        type/data this convention doesn't apply to. Shared by the display
        field above and _compute_price() below so there is exactly one
        formula, not two that can drift apart.
        """
        self.ensure_one()
        pack_size = self.env['product.template']._get_miracle_pack_size(product.uom_id)

        if self.compute_price == 'fixed':
            return self.fixed_price * pack_size
        if self.compute_price == 'percentage' and product.miracle_mrp:
            return pack_size * product.miracle_mrp * (1 - (self.percent_price / 100.0))
        return fallback_price

    def _compute_price(self, product, quantity, uom, date, currency=None):
        """Reinterpret Fixed Price / Discount rules on the mobile app's
        pricelist (company.mobile_app_pricelist_id) the same way
        shrihari_api's /products_by_category shows them to the customer, so
        a real sale order - created from the app or straight from Odoo -
        prices identically to what the catalog advertised. Without this,
        only the catalog display used the pack-size/MRP conversion; the
        actual order line used Odoo's raw, unconverted rule value.
        """
        price = super()._compute_price(product, quantity, uom, date, currency=currency)

        if not self:
            return price

        company = self.pricelist_id.company_id or self.env.company
        if self.pricelist_id.id != company.mobile_app_pricelist_id.id:
            return price

        return self._get_mobile_box_price(product, price)
