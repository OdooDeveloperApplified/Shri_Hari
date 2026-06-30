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
    is_miracle_product = fields.Boolean("Is Miracle Product ?", readonly=True)
    miracle_source_company_id = fields.Many2one('res.company',string='Miracle Source Company',readonly=True,copy=False)

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

        # self = product.template
        if self.type != 'consu' or not self.is_storable:
            return

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
                'type': 'consu',
                'is_storable': True,
                # 'tracking': 'lot',
            }

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

            if source_company.sync_to_another_companies:

                target_companies = source_company.sync_target_company_ids

                payload = {
                    "action": "A",
                    "uniqueId": product.miracle_product_id,
                    "prdnm": product.name,
                    "salrate": str(product.list_price or 0.0),
                    "purrate": str(product.standard_price or 0.0),
                    "slabnm": str(product.miracle_tax_string),
                    "uomnm": product.uom_id.name,
                    "commnm": "CARBON",
                    "hsncode": product.l10n_in_hsn_code,
                }

                for company in target_companies:

                    try:
                        response = company._action_send_product_to_miracle(payload)
                        _logger.info("Shared Product Sync | Product: %s | Company: %s | Response: %s",product.name,company.name,response)

                    except Exception:
                        _logger.exception("Error while syncing product %s to company %s",product.name,company.name)

            product._sync_miracle_stock(item)
        message = (
            f"Miracle Product Sync Completed Successfully. "
            f"Created: {total_created}, Updated: {total_updated}"
        )

        return self.env.company.miracle_notification(
            message,
            "success"
        )

    def action_upload_to_miracle(self):

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

            if not product.l10n_in_hsn_code:
                return self.env.company.miracle_notification(
                    f"HSN Code is required for product '{product.name}'.",
                    "danger"
                )

            # ---------------------------------------------------
            # PAYLOAD
            # ---------------------------------------------------

            payload = {
                "action": action_type,
                "prdnm": product.name,
                "salrate": str(product.list_price or 0.0),
                "purrate": str(product.standard_price or 0.0),
            }

            # EDIT
            if action_type == "E":

                payload["uniqueId"] = product.miracle_product_id

            # ADD
            elif action_type == "A":

                payload.update({
                    "slabnm": str(product.miracle_tax_string),
                    "uomnm": product.uom_id.name,
                    "commnm": "CARBON",
                    "hsncode": product.l10n_in_hsn_code,
                })

            # ---------------------------------------------------
            # UPDATE SOURCE COMPANY
            # ---------------------------------------------------

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

            if source_company.sync_to_another_companies:

                target_companies = source_company.sync_target_company_ids

                for company in target_companies:

                    try:
                        response = company._action_send_product_to_miracle(payload)
                        _logger.info("Shared Product Sync | Product: %s | Company: %s | Response: %s",product.name,company.name,response)

                        if response.get("IsError"):

                            notifications.append({
                                "type": "danger",
                                "message": f"{product.name} | {company.name}: {response.get('Message')}",
                            })

                        else:

                            notifications.append({
                                "type": "success",
                                "message": f"{product.name} | {company.name}: {response.get('Message')}",
                            })

                    except Exception as e:
                        _logger.exception("Error while syncing product %s to company %s",product.name,company.name)

                        notifications.append({
                            "type": "danger",
                            "message": f"{product.name} | {company.name}: {str(e)}",
                        })

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

    # def _action_insert_miracle_product(self, product_data):
    #     if product_data.get("IsError"):
    #         return self.env.company.miracle_notification(
    #             product_data.get("Message"),
    #             "danger"
    #         )
          
    #     for item in product_data.get('Data',[]):
    #         miracle_id = item.get('prdid')
    #         product_name = item.get('prdnm')

    #         if not miracle_id or not product_name:
    #             continue

    #         existing_product = self.search([
    #             ('miracle_product_id','=',miracle_id),
    #             ('is_miracle_product','=',True)
    #         ],limit=1)

    #         tax_string = item.get('slabnm')
    #         sale_tax_ids = self._get_miracle_tax_ids(tax_string, 'sale')
    #         purchase_tax_ids = self._get_miracle_tax_ids(tax_string, 'purchase')

    #         vals = {
    #             'name': product_name,
    #             'l10n_in_hsn_code': item.get('hsncode'),
    #             'list_price': item.get('lsrate') or 0,
    #             'standard_price': item.get('lprate') or 0,
    #             'miracle_tax_string': tax_string,
    #             'type': 'consu',
    #             'is_storable':True
    #         }
            
    #         if sale_tax_ids:
    #             vals['taxes_id'] = [(6, 0, sale_tax_ids)]

    #         if purchase_tax_ids:
    #             vals['supplier_taxes_id'] = [(6, 0, purchase_tax_ids)]

    #         if existing_product:
    #             existing_product.write(vals)
    #             product = existing_product
    #         else:
    #             vals['miracle_product_id'] = miracle_id
    #             vals['is_miracle_product'] = True
    #             product = self.create(vals)
            
            # product._sync_miracle_stock(item)

    # def action_upload_to_miracle(self):
    #     # _logger.info("this is data %s........",self)

    #     self.ensure_one()
    #     company = self.env.company

    #     if self.miracle_product_id:
    #         action_type = "E"
    #     else:
    #         action_type = "A"

    #     payload = {
    #         "action": action_type,
    #         "prdnm": self.name,
    #         "salrate": str(self.list_price),
    #         "purrate": self.standard_price,
    #     }

    #     if action_type == "E":
    #         payload['uniqueId'] = self.miracle_product_id
    #     elif action_type == "A":

    #         if not self.miracle_tax_string:
    #             return company.miracle_notification("Tax slab is required", "danger")

    #         if not self.l10n_in_hsn_code:
    #             return company.miracle_notification(
    #                 f"HSN Code is required before uploading product '{self.name}' to Miracle.",
    #                 "danger"
    #             )

    #         payload['slabnm'] = str(self.miracle_tax_string)
    #         payload['uomnm'] = self.uom_id.name
    #         payload['commnm'] = "CARBON"
    #         payload['hsncode'] = self.l10n_in_hsn_code

    #     # _logger.info("Payload to Miracle: %s", payload)

    #     request = company._action_send_product_to_miracle(payload)

    #     if action_type == "A":
    #         if request.get("IsError"):
    #             return company.miracle_notification(
    #                 request.get("Message"),
    #                 "danger"
    #             )
    #         unique_id = request.get("UniqueId")

    #         if not unique_id:
    #             return company.miracle_notification(
    #                 "Miracle did not return UniqueId",
    #                 "danger"
    #             )

    #         self.write({
    #             "miracle_product_id": unique_id,
    #             "is_miracle_product": True,
    #         })
        
    #     return company.miracle_notification(
    #         request.get('Message'),
    #         "success"
    #     )

    def action_sync_from_miracle(self):
        self.ensure_one()
        company = self.env.company

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

        sale_tax_ids = self._get_miracle_tax_ids(tax_string, 'sale')
        purchase_tax_ids = self._get_miracle_tax_ids(tax_string, 'purchase')

        vals = {
            'name': data.get('prdnm'),
            'l10n_in_hsn_code': data.get('hsncode'),
            'list_price': data.get('salrate'),
            'standard_price': data.get('purrate'),
            'miracle_tax_string': tax_string,
        }

        if sale_tax_ids:
            vals['taxes_id'] = [(6, 0, sale_tax_ids)]

        if purchase_tax_ids:
            vals['supplier_taxes_id'] = [(6, 0, purchase_tax_ids)]

        self.write(vals)

        return company.miracle_notification(
            "Product synced successfully.",
            "success"
        )