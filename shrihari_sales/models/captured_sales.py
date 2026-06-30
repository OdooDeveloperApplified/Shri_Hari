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
        companies = self.env['res.company'].search([])

        for record in self:
            if record.state == 'processed':
                raise UserError(_("Sale Orders already created for this record."))

            if not record.line_ids:
                raise UserError(_("Please add at least one line."))

            company_line_map = {}
      
            # STEP 1: Assign each line to correct company using REAL stock (stock.quant)
            StockQuant = self.env['stock.quant']
            
            for line in record.line_ids:
                product = line.product_id
                required_qty = line.product_uom_qty

                best_company = False
                best_qty = 0
                for company in companies:
                    # _logger.info(f"Checking stock for product {product.name} in best_company {best_company.name if best_company else 'None'} for best_qty {best_qty} qty {required_qty}")
                    # Get real stock per company
                    quants = StockQuant.with_company(company).sudo().search([
                        ('product_id', '=', product.id),
                        ('company_id', '=', company.id),
                        ('location_id.usage', '=', 'internal')
                    ])
                    
                    available_qty = sum(quants.mapped('quantity')) - sum(quants.mapped('reserved_quantity'))

                    _logger.info(f"Product: {product.name}, Company: {company.name}, Available: {available_qty}")

                    # Pick company which can fulfill demand
                    if available_qty >= required_qty and available_qty > best_qty:
                        best_qty = available_qty
                        best_company = company
                    
                    _logger.info(f"Checked company {company.name} for product {product.name}: available {available_qty}, best so far: {best_qty} from {best_company.name if best_company else 'None'}")
                    
                _logger.info(f"Best Company so far for product {product.name}: {best_company.name if best_company else 'None'} with qty {best_qty}")

                # No company can fulfill
                if not best_company:
                    raise UserError(
                        _("Not enough stock for product %s in any company.") % product.display_name
                    )

                # Assign line to company
                if best_company not in company_line_map:
                    company_line_map[best_company] = []
                _logger.info(company_line_map)

                company_line_map[best_company].append(line)

            created_orders = []

            # STEP 2: Create Sale Orders per company
            for company, lines in company_line_map.items():
                _logger.info(f"Creating Sale Order for company {company.name} with {len(lines)} lines.")
                order_lines = []
                for line in lines:
                    order_lines.append((0, 0, {
                        'product_id': line.product_id.id,
                        'product_uom_qty': line.product_uom_qty,
                        'price_unit': line.price_unit,
                        'name': line.product_id.display_name,
                    }))

                order_vals = {
                    'partner_id': record.customer_id.id,
                    'company_id': company.id,
                    'order_line': order_lines,
                    'state': 'sale',
                }
                _logger.info(f"Order Vals for company {company.name}: {order_vals}")

                sale_order = SaleOrder.with_company(company).with_context(skip_miracle_sync=True).create(order_vals)

                # --- NEW LOGIC for Automation ---
                # 1. Automate Delivery Validation
                for picking in sale_order.picking_ids:
                    picking.with_context(skip_miracle_sync=True).action_assign()
                    for move_line in picking.move_ids:
                        move_line.quantity = move_line.product_uom_qty
                    picking.with_context(skip_miracle_sync=True).button_validate()
                    
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