from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class SaleCapture(models.Model):
    _name = 'sale.capture'
    _description = 'Sale Capture'
    _inherit = ['mail.thread']

    name = fields.Char(string="Reference", readonly=True, copy=False, default='New')

    user_id = fields.Many2one('res.users', string='Distributor (User)', required=True)
    capture_date = fields.Datetime(string='Capture Date', default=fields.Datetime.now, required=True)

    line_ids = fields.One2many('sale.capture.line', 'capture_id', string='Capture Lines')

    state = fields.Selection([
        ('draft', 'Draft'),
        ('processed', 'Processed')
    ], default='draft', tracking=True)

    sale_order_ids = fields.Many2many('sale.order', string="Generated Sale Orders", readonly=True)
    customer_id = fields.Many2one('res.partner', string='Customer')
    customer_street = fields.Char(string='Address Line 1',store=True)
    customer_street2 = fields.Char(string='Address Line 2',store=True)
    customer_city = fields.Char(string='City',store=True)
    customer_zip = fields.Char(string='Zip',store=True)
    customer_country_id = fields.Many2one('res.country', string='Country',store=True)
    customer_state_id = fields.Many2one('res.country.state', string='State',store=True)  
    customer_mobile = fields.Char(string='Mobile',store=True)
    customer_email = fields.Char(string='Email',store=True)  

    # Sequence
    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sale.capture') or 'New'
        return super(SaleCapture, self).create(vals)

    # MAIN LOGIC
    def action_create_sale_orders(self):
        SaleOrder = self.env['sale.order']

        for record in self:
            if record.state == 'processed':
                raise UserError(_("Sale Orders already created for this record."))

            if not record.line_ids:
                raise UserError(_("Please add at least one line."))

            # Single Company Logic: Use the user's company or default company
            company = record.user_id.company_id or self.env.company
            StockQuant = self.env['stock.quant']
            
            created_orders = []

            # STEP 1: Prepare order lines for the single company
            order_lines = []
            for line in record.line_ids:
                # Check stock for this specific product in the single company
                quants = StockQuant.with_company(company).sudo().search([
                    ('product_id', '=', line.product_id.id),
                    ('company_id', '=', company.id),
                    ('location_id.usage', '=', 'internal')
                ])
                available_qty = sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))
                
                if available_qty < line.product_uom_qty:
                    raise UserError(
                        _("Not enough stock for product %s. Available: %s, Requested: %s") % 
                        (line.product_id.display_name, available_qty, line.product_uom_qty)
                    )

                order_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'product_uom_qty': line.product_uom_qty,
                    'price_unit': line.price_unit,
                    'name': line.product_id.display_name,
                }))

            # STEP 2: Create a Single Sale Order
            order_vals = {
                'partner_id': record.customer_id.id,
                'company_id': company.id,
                'order_line': order_lines,
                'state': 'sale',
            }
            _logger.info(f"Order Vals for single company {company.name}: {order_vals}")

            sale_order = SaleOrder.with_company(company).with_context(skip_miracle_sync=True).create(order_vals)

            # 1. Automate Delivery Validation
            for picking in sale_order.picking_ids:
                picking.with_context(skip_miracle_sync=True).action_assign()
                for move_line in picking.move_ids:
                    move_line.quantity = move_line.product_uom_qty
                
                # Force validation by skipping popup wizards
                picking.with_context(
                    skip_miracle_sync=True, 
                    skip_immediate=True, 
                    skip_backorder=True
                ).button_validate()
                
            # 2. Automate Invoice Creation and Posting
            invoice = sale_order.with_context(skip_miracle_sync=True)._create_invoices()
            if invoice:
                invoice.with_context(skip_miracle_sync=True).action_post()
            # --------------------------------

            # --- Trigger Background Sync Cron Job ---
            # 3. Upload delivery to miracle
            cron_job = self.env.ref('app_miracle_voucher.cron_sync_miracle_deliveries', raise_if_not_found=False)
            if cron_job:
                cron_job._trigger()
            # ---------------------------------------------------

            created_orders.append(sale_order.id)

            _logger.info(
                f"Created Sale Order {sale_order.name} for company {company.name}"
            )

            # Link + Update State
            record.sale_order_ids = [(6, 0, created_orders)]
            record.state = 'processed'
    
    currency_id = fields.Many2one('res.currency',default=lambda self: self.env.company.currency_id.id, string='Currency', readonly=True)
    amount_total = fields.Float(string='Total',compute='_compute_amounts',store=True)
    @api.depends('line_ids.price_subtotal')
    def _compute_amounts(self):
        for record in self:
            record.amount_total = sum(record.line_ids.mapped('price_subtotal'))

class SaleCaptureLine(models.Model):
    _name = 'sale.capture.line'
    _description = 'Sale Capture Line'

    capture_id = fields.Many2one('sale.capture', string='Sale Capture', ondelete='cascade')
    product_id = fields.Many2one('product.product', string='Product', required=True)
    product_uom_qty = fields.Float(string='Quantity', required=True)
    price_unit = fields.Float(string='Unit Price', required=True)
    pro_category_id = fields.Many2one('product.category', string='ProductCategory', related='product_id.categ_id', store=True)
    currency_id = fields.Many2one('res.currency',related='capture_id.currency_id',store=True,readonly=True)
    price_subtotal = fields.Float(string='Amount',compute='_compute_price_subtotal',store=True)
    product_uom = fields.Many2one(comodel_name='uom.uom',string="Unit of Measure",compute='_compute_product_uom',store=True)
    
    @api.depends('product_id')
    def _compute_product_uom(self):
        for line in self:
            if not line.product_uom or (line.product_id.uom_id.id != line.product_uom.id):
                line.product_uom = line.product_id.uom_id

    @api.depends('product_uom_qty', 'price_unit')
    def _compute_price_subtotal(self):
        for line in self:
            line.price_subtotal = line.product_uom_qty * line.price_unit
    
    @api.onchange('product_id')
    def _onchange_product_id(self):
        for line in self:
            if line.product_id:
                line.price_unit = line.product_id.list_price