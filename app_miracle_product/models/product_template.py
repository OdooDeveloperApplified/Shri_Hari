from odoo import models, fields, api
from datetime import timedelta
from odoo.exceptions import UserError
import re
import logging
_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = "product.template"

    miracle_product_id = fields.Char("Miracle Product ID", readonly=True)
    miracle_tax_string = fields.Char("Miracle Tax String", compute="_compute_miracle_tax_string")
    miracle_commodity_name = fields.Char("Miracle Commodity Name", readonly=True)
    is_miracle_product = fields.Boolean("Is Miracle Product ?", readonly=True)
    miracle_source_company_id = fields.Many2one('res.company',string='Miracle Source Company',readonly=True,copy=False)
    miracle_group_id = fields.Many2one('miracle.product.group', string="Miracle Group")

    def _get_miracle_group_id(self, grpnm):
        if not grpnm:
            return False
        Group = self.env['miracle.product.group']
        group = Group.search([('name', '=ilike', grpnm)], limit=1)
        if group:
            return group.id
        group = Group.create({'name': grpnm})
        return group.id

    def _get_miracle_category_id(self, catnm):
        if not catnm:
            return False
        Category = self.env['product.category']
        category = Category.search([('name', '=ilike', catnm)], limit=1)
        if category:
            return category.id
        category = Category.create({'name': catnm})
        return category.id

    def _get_miracle_tax_ids(self, tax_string, tax_type='sale'):
        AccountTax = self.env['account.tax']

        if not tax_string:
            return []

        match = re.search(r'(\d+)', tax_string)
        if not match:
            return []

        rate = float(match.group(1))

        taxes = AccountTax.search([
            ('amount', '=', rate),
            ('type_tax_use', '=', tax_type)
        ])

        taxes = taxes.filtered(lambda t:
            'GST' in t.name and
            'EXP' not in t.name and
            'SEZ' not in t.name and
            'RC' not in t.name and 
            'IGST' not in t.name
        )

        if taxes:
            return taxes.ids

        _logger.info("No %s tax found for %s", tax_type, tax_string)
        return []

    def _get_miracle_uom_id(self, uom_name):
        if not uom_name or uom_name.lower() == 'default':
            return self.env.ref('uom.product_uom_unit').id

        Uom = self.env['uom.uom']
        uom = Uom.search([('name', '=ilike', uom_name)], limit=1)

        if uom:
            return uom.id

        uom_category = self.env['uom.category'].search([('name', '=', 'Miracle Units')], limit=1)
        if not uom_category:
            uom_category = self.env['uom.category'].create({'name': 'Miracle Units'})
            self.env['uom.uom'].create({
                'name': 'Miracle Base Unit',
                'category_id': uom_category.id,
                'uom_type': 'reference',
                'factor': 1.0,
            })

        ratio = 1.0
        numbers = re.findall(r'\d+\.?\d*', uom_name)
        if numbers:
            try:
                ratio = float(numbers[-1])
            except Exception:
                pass

        if ratio <= 0.0:
            ratio = 1.0

        if ratio > 1.0:
            vals = {
                'name': uom_name,
                'category_id': uom_category.id,
                'uom_type': 'bigger',
                'factor_inv': ratio,
            }
        else:
            vals = {
                'name': uom_name,
                'category_id': uom_category.id,
                'uom_type': 'smaller',
                'factor': ratio,
            }

        uom = Uom.create(vals)
        return uom.id

    @api.depends('taxes_id', 'supplier_taxes_id')
    def _compute_miracle_tax_string(self):
        for record in self:

            sale_tax = record.taxes_id[:1]
            purchase_tax = record.supplier_taxes_id[:1]

            # ❌ If both exist and mismatch → don't compute
            if sale_tax and purchase_tax:
                if sale_tax.amount != purchase_tax.amount:
                    record.miracle_tax_string = False
                    continue

            # 👉 Priority: Sale → Purchase
            taxes = sale_tax or purchase_tax

            if not taxes:
                record.miracle_tax_string = False
                continue

            gst_tax = taxes.filtered(lambda t:
                'GST' in t.name and
                'EXP' not in t.name and
                'SEZ' not in t.name and
                'RC' not in t.name and
                'IGST' not in t.name
            )

            if not gst_tax:
                record.miracle_tax_string = False
                continue

            rate = gst_tax[0].amount

            record.miracle_tax_string = f"GST {int(rate)}%"

    def _sync_miracle_stock(self, item):
        closing_qty = item.get('clqty1') or 0.0
        
        if self.type != 'consu' or not self.is_storable:
            return

        uom = self.uom_id
        if uom:
            if uom.uom_type == 'bigger':
                closing_qty = closing_qty / uom.factor_inv
            elif uom.uom_type == 'smaller' and uom.factor > 0:
                closing_qty = closing_qty * uom.factor

        product = self.product_variant_id
        if not product:
            return

        company = self.env.company
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', company.id)], limit=1)
        if warehouse:
            location = warehouse.lot_stock_id
        else:
            location = self.env.ref('stock.stock_location_stock')

        StockQuant = self.env['stock.quant']

        current_qty = StockQuant._get_available_quantity(product, location)
        diff_qty = closing_qty - current_qty

        if diff_qty != 0:
            StockQuant._update_available_quantity(product, location, diff_qty)

    def _action_insert_miracle_product(self, product_data):

        if product_data.get("IsError"):
            return self.env.company.miracle_notification(
                product_data.get("Message"),
                "danger"
            )

        source_company = self.env.company

        if source_company.sync_to_another_companies and not source_company.sync_target_company_ids:
            return self.env.company.miracle_notification(
                "Please configure target companies for Miracle sync.",
                "danger"
            )

        total_created = 0
        total_updated = 0
        for item in product_data.get('Data', []):

            miracle_id = item.get('prdid')
            product_name = item.get('prdnm')

            if not miracle_id or not product_name:
                continue

            # ---------------------------------------------------
            # SHARED PRODUCT SEARCH
            # ---------------------------------------------------

            existing_product = self.search([
                ('miracle_product_id', '=', miracle_id),
                ('is_miracle_product', '=', True)
            ], limit=1)

            tax_string = item.get('slabnm')
            uom_string = item.get('uomnm')

            sale_tax_ids = self._get_miracle_tax_ids(
                tax_string,
                'sale'
            )

            purchase_tax_ids = self._get_miracle_tax_ids(
                tax_string,
                'purchase'
            )

            vals = {
                'name': product_name,
                'company_id': False,
                'miracle_source_company_id': source_company.id,
                'l10n_in_hsn_code': item.get('hsncode'),
                'list_price': item.get('lsrate') or 0,
                'standard_price': item.get('lprate') or 0,
                'miracle_tax_string': tax_string,
                'miracle_commodity_name': item.get('commnm'),
                'type': 'consu',
                'is_storable': True,
                # 'tracking': 'lot',
            }

            if item.get('grpnm'):
                vals['miracle_group_id'] = self._get_miracle_group_id(item.get('grpnm'))
            
            if item.get('catnm'):
                categ_id = self._get_miracle_category_id(item.get('catnm'))
                if categ_id:
                    vals['categ_id'] = categ_id

            if uom_string:
                uom_id = self._get_miracle_uom_id(uom_string)
                if uom_id:
                    vals['uom_id'] = uom_id
                    vals['uom_po_id'] = uom_id

            if sale_tax_ids:
                vals['taxes_id'] = [(6, 0, sale_tax_ids)]

            if purchase_tax_ids:
                vals['supplier_taxes_id'] = [(6, 0, purchase_tax_ids)]

            # ---------------------------------------------------
            # UPDATE / CREATE
            # ---------------------------------------------------

            if existing_product:
                existing_product.write(vals)
                product = existing_product
                total_updated += 1
                
                _logger.info("Miracle Product Updated | %s | %s",product.name,source_company.name)

            else:
                vals['miracle_product_id'] = miracle_id
                vals['is_miracle_product'] = True
                product = self.create(vals)
                product._sync_miracle_stock(item)
                total_created += 1

                _logger.info("Miracle Product Created | %s | %s",product.name,source_company.name)

            # ---------------------------------------------------
            # AUTO SYNC TO TARGET COMPANIES
            # ---------------------------------------------------

            product._push_to_miracle_target_companies(source_company)

            product._sync_miracle_stock(item)
        message = (
            f"Miracle Product Sync Completed Successfully. "
            f"Created: {total_created}, Updated: {total_updated}"
        )

        return self.env.company.miracle_notification(
            message,
            "success"
        )

    #Helper method for pushing product to other companies
    def _push_to_miracle_target_companies(self, source_company):
        """Pushes the current product to target companies of the given source company."""
        self.ensure_one()
        notifications = []
        
        if not source_company.sync_to_another_companies:
            return notifications
            
        target_companies = source_company.sync_target_company_ids
        if not target_companies:
            return notifications

        base_edit_payload = {
            "uniqueId": self.miracle_product_id,
            "prdnm": self.name,
            "salrate": str(self.list_price or 0.0),
            "purrate": str(self.standard_price or 0.0),
            # "uomnm": self.uom_id.name if self.uom_id else "",
        }

        add_fields = {
            "slabnm": str(self.miracle_tax_string or ""),
            "commnm": self.miracle_commodity_name or "",
            "grpnm": self.miracle_group_id.name if self.miracle_group_id else "",
        }

        for company in target_companies:
            try:
                target_payload = base_edit_payload.copy()
                target_payload["action"] = "E"
                response = company._action_send_product_to_miracle(target_payload)
                
                if response.get("IsError") and ("No records found" in response.get("Message", "") or response.get("ErrorCode") == "TPA003"):
                    target_payload["action"] = "A"
                    target_payload.update(add_fields)
                    response = company._action_send_product_to_miracle(target_payload)
                
                if not response.get("IsError"):
                    self.with_company(company).write({
                        'standard_price': self.standard_price
                    })
                    notifications.append({
                        "type": "success",
                        "message": f"{self.name} | {company.name}: {response.get('Message', 'Success')}",
                    })
                else:
                    notifications.append({
                        "type": "danger",
                        "message": f"{self.name} | {company.name}: {response.get('Message')}",
                    })
                    
                _logger.info("Shared Product Sync | Product: %s | Company: %s | Response: %s", self.name, company.name, response)

            except Exception as e:
                _logger.exception("Error while syncing product %s to company %s", self.name, company.name)
                notifications.append({
                    "type": "danger",
                    "message": f"{self.name} | {company.name}: {str(e)}",
                })

        return notifications

    def action_upload_to_miracle(self, from_webhook=False):

        notifications = []

        source_company = self.env.company

        if source_company.sync_to_another_companies and not source_company.sync_target_company_ids:
            return self.env.company.miracle_notification(
                "Please configure target companies for Miracle sync.",
                "danger"
            )

        for product in self:

            action_type = "E" if product.miracle_product_id else "A"

            if not product.miracle_tax_string:
                return self.env.company.miracle_notification(
                    f"Tax slab is required for product '{product.name}'.",
                    "danger"
                )

            # if not product.l10n_in_hsn_code:
            #     return self.env.company.miracle_notification(
            #         f"HSN Code is required for product '{product.name}'.",
            #         "danger"
            #     )

            # ---------------------------------------------------
            # PAYLOAD
            # ---------------------------------------------------

            payload = {
                "action": action_type,
                "prdnm": product.name,
                # "uomnm": product.uom_id.name,
                "salrate": str(product.list_price or 0.0),
                "purrate": str(product.standard_price or 0.0),
            }

            # EDIT
            if action_type == "E":

                payload["uniqueId"] = product.miracle_product_id

            # ADD
            elif action_type == "A":

                payload.update({
                    # "slabnm": str(product.miracle_tax_string),
                    "uomnm": product.uom_id.name,
                    "commnm": product.miracle_commodity_name or "",
                    # "hsncode": product.l10n_in_hsn_code,
                    "grpnm": product.miracle_group_id.name if product.miracle_group_id else "",
                    # "catnm": product.categ_id.name if product.categ_id else "",
                })

            # ---------------------------------------------------
            # UPDATE SOURCE COMPANY
            # ---------------------------------------------------

            if not from_webhook:
                try:
                    response = source_company._action_send_product_to_miracle(payload)
                    _logger.info("Source Product Sync | %s | %s",source_company.name,response)

                    if response.get("IsError"):

                        notifications.append({
                            "type": "danger",
                            "message": f"{product.name} | {source_company.name}: {response.get('Message')}",
                        })

                    else:

                        vals = {
                            'company_id': False,
                            'is_miracle_product': True,
                        }

                        # SAVE UNIQUE ID ONLY FOR ADD
                        if action_type == "A":

                            unique_id = response.get("UniqueId")

                            if not unique_id:

                                notifications.append({
                                    "type": "danger",
                                    "message": f"{product.name} | {source_company.name}: Miracle did not return UniqueId",
                                })

                                continue

                            vals["miracle_product_id"] = unique_id

                        product.write(vals)

                        notifications.append({
                            "type": "success",
                            "message": f"{product.name} | {source_company.name}: {response.get('Message')}",
                        })

                except Exception as e:

                    _logger.exception(
                        "Error while syncing product to source company"
                    )

                    notifications.append({
                        "type": "danger",
                        "message": f"{product.name} | {source_company.name}: {str(e)}",
                    })

            # ---------------------------------------------------
            # AUTO SYNC TO TARGET COMPANIES
            # ---------------------------------------------------

            target_notifs = product._push_to_miracle_target_companies(source_company)
            notifications.extend(target_notifs)

        # ---------------------------------------------------
        # NOTIFICATIONS
        # ---------------------------------------------------

        if not notifications:
            return

        def build_notification(index):

            notif = notifications[index]

            action = {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Miracle Sync',
                    'message': notif['message'],
                    'type': notif['type'],
                    'sticky': True,
                }
            }

            if index + 1 < len(notifications):
                action['params']['next'] = build_notification(index + 1)

            return action

        return build_notification(0)

    def action_sync_from_miracle(self, api_response=None):
        self.ensure_one()
        company = self.env.company

        if api_response:
            response = api_response
        else:
            payload = {
                "id": self.miracle_product_id
            }
            response = company._action_get_product_from_miracle(payload) 

        if not response:
            return company.miracle_notification(
                "No response from Miracle API.",
                "danger"
            )       

        if response.get("IsError"):
            return company.miracle_notification(
                response.get("Message"),
                "danger"
            )

        data = response.get("DataModel")

        if not data:
            raise UserError("Product not found in Miracle.")
        
        tax_string = data.get('slabnm')
        uom_string = data.get('uomnm')

        sale_tax_ids = self._get_miracle_tax_ids(tax_string, 'sale')
        purchase_tax_ids = self._get_miracle_tax_ids(tax_string, 'purchase')

        vals = {
            'name': data.get('prdnm'),
            'l10n_in_hsn_code': data.get('hsncode'),
            'list_price': data.get('salrate'),
            'standard_price': data.get('purrate'),
            'miracle_tax_string': tax_string,
            'miracle_commodity_name': data.get('commnm'),
        }

        if data.get('grpnm'):
            vals['miracle_group_id'] = self._get_miracle_group_id(data.get('grpnm'))
            
        if data.get('catnm'):
            categ_id = self._get_miracle_category_id(data.get('catnm'))
            if categ_id:
                vals['categ_id'] = categ_id

        if uom_string:
            uom_id = self._get_miracle_uom_id(uom_string)
            if uom_id:
                vals['uom_id'] = uom_id
                vals['uom_po_id'] = uom_id

        if sale_tax_ids:
            vals['taxes_id'] = [(6, 0, sale_tax_ids)]

        if purchase_tax_ids:
            vals['supplier_taxes_id'] = [(6, 0, purchase_tax_ids)]

        self.write(vals)

        return company.miracle_notification(
            "Product synced successfully.",
            "success"
        )

    #Helper method to fetch correct UOM from Miracle
    def action_bulk_sync_miracle(self):
        company = self.env.company

        total_synced = 0
        for product in self:
            if not product.miracle_product_id:
                continue

            payload = {
                "id": product.miracle_product_id
            }

            response = company._action_get_product_from_miracle(payload) 

            if not response or response.get("IsError"):
                _logger.warning("Miracle sync failed for product %s", product.name)
                continue

            data = response.get("DataModel")
            if not data:
                continue
            
            tax_string = data.get('slabnm')
            uom_string = data.get('uomnm')

            sale_tax_ids = product._get_miracle_tax_ids(tax_string, 'sale')
            purchase_tax_ids = product._get_miracle_tax_ids(tax_string, 'purchase')

            vals = {
                'name': data.get('prdnm'),
                'l10n_in_hsn_code': data.get('hsncode'),
                'list_price': data.get('salrate'),
                'standard_price': data.get('purrate'),
                'miracle_tax_string': tax_string,
                'miracle_commodity_name': data.get('commnm'),
            }

            if data.get('grpnm'):
                vals['miracle_group_id'] = product._get_miracle_group_id(data.get('grpnm'))
                
            if data.get('catnm'):
                categ_id = product._get_miracle_category_id(data.get('catnm'))
                if categ_id:
                    vals['categ_id'] = categ_id

            if uom_string:
                uom_id = product._get_miracle_uom_id(uom_string)
                if uom_id:
                    vals['uom_id'] = uom_id
                    vals['uom_po_id'] = uom_id

            if sale_tax_ids:
                vals['taxes_id'] = [(6, 0, sale_tax_ids)]

            if purchase_tax_ids:
                vals['supplier_taxes_id'] = [(6, 0, purchase_tax_ids)]

            product.write(vals)
            total_synced += 1

        return company.miracle_notification(
            f"Successfully synced {total_synced} products.",
            "success"
        )
