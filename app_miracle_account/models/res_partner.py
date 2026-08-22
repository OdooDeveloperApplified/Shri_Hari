from odoo import models, fields
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)

class Partner(models.Model):
    _inherit = "res.partner"

    miracle_account_id = fields.Char(string="Miracle Account ID", readonly=True)
    is_miracle_account = fields.Boolean(string="is Miracle Account",readonly=True)
    miracle_mob2 = fields.Char(string="Secondary Mobile")
    miracle_phone2 = fields.Char(string="Secondary Phone")
    miracle_rphone1 = fields.Char(string="Residence Phone 1")
    miracle_rphone2 = fields.Char(string="Residence Phone 2")
    miracle_factory_no = fields.Char(string="Factory Number")
    miracle_aadhar_no = fields.Char(string="Aadhar Number")
    miracle_acc_group = fields.Selection([
        ('sundry_creditors', 'Sundry Creditors'),
        ('sundry_debtors', 'Sundry Debtors'),
        ('sundry_creditors_-_rr', 'Sundry Creditors - RR'),
        ('sundry_debtors_-_rr', 'Sundry Debtors - RR'),
    ], string="Miracle Account Group")
    miracle_sup_group = fields.Char(string="Miracle Super Group")
    miracle_udyam_no = fields.Char(string="Miracle Udayam Number")
    miracle_udyam_type = fields.Char(string="Miracle Udyam Type")
    miracle_udyam_activity = fields.Char(string="Miracle Udyam Activity")
    miracle_acc_status = fields.Char(string="Miracle Account Status")
    miracle_transport = fields.Char(string="Miracle Transport")
    miracle_opening_balance = fields.Float(string="Miracle Opening Balance")
    miracle_closing_balance = fields.Float(string="Miracle Closing Balance")
    miracle_acc_alias = fields.Char(string="Miracle Account Alias")
    miracle_areanm = fields.Char(string="Miracle Area Name")
    miracle_source_company_id = fields.Many2one('res.company',string='Miracle Source Company',readonly=True,copy=False)

    def _split_miracle_address(self, text, limit=50):
        if not text: return "", ""
        if len(text) <= limit: return text, ""
        
        parts = text.split(",")
        if len(parts) > 1:
            for i in range(len(parts)-1, 0, -1):
                p1 = ",".join(parts[:i]).strip()
                p2 = ("," + ",".join(parts[i:])).strip()
                if len(p1) <= limit and len(p2) <= limit:
                    return p1, p2
                    
        import textwrap
        wrapped = textwrap.wrap(text, limit)
        if len(wrapped) == 1:
            return wrapped[0], ""
        elif len(wrapped) >= 2:
            return wrapped[0], " ".join(wrapped[1:])[:limit]
            
        return text[:limit], text[limit:limit*2]

    def _action_insert_miracle_account_partner(self, partner_data):

        if partner_data.get('IsError'):
            return self.env.company.miracle_notification(
                partner_data.get("Message"),
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
        for partner in partner_data.get('Data', []):

            miracle_id = partner.get('accid')
            account_name = partner.get('accnm')

            if not miracle_id or not account_name:
                continue

            state_id = False

            if partner.get('statenm'):

                state = self.env['res.country.state'].search([
                    ('name', 'ilike', partner.get('statenm')),
                    ('country_id.code', '=', 'IN')
                ], limit=1)

                if state:
                    state_id = state.id

            gst_map = {
                'Regular': 'regular',
                'Composition': 'composition',
                'Unregistered': 'unregistered',
                'Consumer': 'consumer',
                'Overseas': 'overseas',
                'SEZ': 'special_economic_zone',
            }

            gst_treatment = gst_map.get(
                partner.get("regtype")
            )

            street = " ".join(filter(None, [
                partner.get("addr1"),
                partner.get("addr2")
            ]))

            street2 = " ".join(filter(None, [
                partner.get("addr3"),
                partner.get("addr4")
            ]))

            category_ids = []

            # if partner.get("catnm"):

            #     category = self.env['res.partner.category'].search([
            #         ('name', '=', partner.get("catnm"))
            #     ], limit=1)
            #     _logger.info("CCCategory name %s",category)

            #     if not category:

            #         category = self.env['res.partner.category'].create({
            #             'name': partner.get("catnm")
            #         })

            #     category_ids = [(4, category.id)]

            payment_term_id = False

            if partner.get('crdays'):

                payment_term = self.env['account.payment.term'].search([
                    ('name', 'ilike', str(partner.get('crdays')))
                ], limit=1)

                if payment_term:
                    payment_term_id = payment_term.id

            payment_method_id = False

            if partner.get('balmethod'):

                payment_method = self.env['account.payment.method.line'].search([
                    ('name', 'ilike', partner.get('balmethod'))
                ], limit=1)

                if payment_method:
                    payment_method_id = payment_method.id

            existing_partner = self.search([
                ('miracle_account_id', '=', miracle_id),
                ('is_miracle_account', '=', True)
            ], limit=1)

            customer_rank = 0
            supplier_rank = 0

            acc_group = partner.get('accgrpnm')

            if acc_group:

                acc_group_name = acc_group.strip().lower()

                if 'debtor' in acc_group_name:
                    customer_rank = 1

                elif 'creditor' in acc_group_name:
                    supplier_rank = 1

                else:
                    continue

            else:
                continue

            vals = {
                'company_id': False,
                'name': account_name,
                'company_type': 'company',
                'street': street,
                'street2': street2,
                'city': partner.get("citynm"),
                'zip': partner.get("pincode"),
                'state_id': state_id,
                'phone': partner.get("phone1"),
                'mobile': partner.get("mob1"),
                'email': partner.get("email"),
                'website': partner.get("website"),
                'vat': partner.get("gstin"),
                # 'category_id': category_ids,
                'l10n_in_gst_treatment': gst_treatment,
                'l10n_in_pan': partner.get('panno'),
                'credit_limit': partner.get('crlimit'),
                'credit': partner.get('totalcr'),
                'debit': partner.get('totaldb'),
                'property_payment_term_id': payment_term_id,
                'property_inbound_payment_method_line_id': payment_method_id,
                'customer_rank': customer_rank,
                'supplier_rank': supplier_rank,
                'miracle_source_company_id': source_company.id,
                'miracle_mob2': partner.get("mob2"),
                'miracle_phone2': partner.get("phone2"),
                'miracle_rphone1': partner.get("rphone1"),
                'miracle_rphone2': partner.get("rphone2"),
                'miracle_factory_no': partner.get("factoryno"),
                'miracle_aadhar_no': partner.get('aadharno'),
                'miracle_acc_group': acc_group_name.replace(' ', '_'),
                'miracle_sup_group': partner.get('sgrpname'),
                'miracle_udyam_no': partner.get('udyamno'),
                'miracle_udyam_type': partner.get('udyamtyp'),
                'miracle_udyam_activity': partner.get('udyamact'),
                'miracle_acc_status': partner.get('accstatus'),
                'miracle_transport': partner.get('transport'),
                'miracle_opening_balance': partner.get('opbal'),
                'miracle_closing_balance': partner.get('clbal'),
                'miracle_acc_alias': partner.get('accalinm'),
                'miracle_areanm': partner.get('areanm'),
            }

            if existing_partner:
                existing_partner.write(vals)
                partner_rec = existing_partner
                total_updated += 1
                _logger.info("Miracle Partner Updated | %s | %s",partner_rec.name,source_company.name)

            else:
                vals.update({
                    'miracle_account_id': miracle_id,
                    'is_miracle_account': True
                })
                partner_rec = self.create(vals)
                total_created += 1
                _logger.info("Miracle Partner Created | %s | %s",partner_rec.name,source_company.name)

            if partner.get("conper1"):

                contact1 = self.search([
                    ('parent_id', '=', partner_rec.id),
                    ('name', '=', partner.get("conper1"))
                ], limit=1)

                contact_vals = {
                    'name': partner.get("conper1"),
                    'parent_id': partner_rec.id,
                    'company_type': 'person',
                    'type': 'contact',
                    'mobile': partner.get("mob1"),
                    'phone': partner.get("phone1"),
                    'email': partner.get("email"),
                }

                if contact1:
                    contact1.write(contact_vals)
                else:
                    self.create(contact_vals)

            if partner.get("conper2"):

                contact2 = self.search([
                    ('parent_id', '=', partner_rec.id),
                    ('name', '=', partner.get("conper2"))
                ], limit=1)

                contact_vals = {
                    'name': partner.get("conper2"),
                    'parent_id': partner_rec.id,
                    'company_type': 'person',
                    'type': 'contact',
                    'mobile': partner.get("mob2"),
                    'phone': partner.get("phone2"),
                    'email': partner.get("email"),
                }

                if contact2:
                    contact2.write(contact_vals)
                else:
                    self.create(contact_vals)

            if partner.get('baccno'):

                bank_rec = False

                if partner.get('bname'):

                    bank_rec = self.env['res.bank'].search([
                        ('name', 'ilike', partner.get('bname'))
                    ], limit=1)

                    if not bank_rec:

                        bic_code = False

                        if partner.get('bifsc'):
                            bic_code = partner.get('bifsc')

                        if not partner.get('bifsc'):
                            bic_code = partner.get('swiftcode')

                        bank_rec = self.env['res.bank'].create({
                            'name': partner.get('bname'),
                            'bic': bic_code,
                            'street': partner.get('bradd'),
                            'city': partner.get('bbranch')
                        })

                    bank = self.env['res.partner.bank'].search([
                        ('partner_id', '=', partner_rec.id),
                        ('acc_number', '=', partner.get('baccno'))
                    ], limit=1)

                    bank_vals = {
                        'partner_id': partner_rec.id,
                        'acc_number': partner.get('baccno'),
                        'miracle_iban_no': partner.get('ibanno'),
                        'bank_id': bank_rec.id if bank_rec else False,
                    }

                    if bank:
                        bank.write(bank_vals)
                    else:
                        self.env['res.partner.bank'].create(bank_vals)

            # ---------------------------------------------------
            # AUTO SYNC TO TARGET COMPANIES
            # ---------------------------------------------------

            partner_rec._push_to_miracle_target_companies(source_company)
                    
        message = (
            f"Miracle Partner Sync Completed Successfully. "
            f"Created: {total_created}, Updated: {total_updated}"
        )

        return self.env.company.miracle_notification(
            message,
            "success"
        )

    #Helper method for pushing account to other companies
    def _push_to_miracle_target_companies(self, source_company):
        """Pushes the current partner to target companies of the given source company."""
        self.ensure_one()
        notifications = []
        if not source_company.sync_to_another_companies:
            return notifications
            
        target_companies = source_company.sync_target_company_ids
        if not target_companies:
            return notifications

        crdays = 0
        if self.property_payment_term_id:
            payment_term_name = self.property_payment_term_id.name or ""
            digits = ''.join(filter(str.isdigit, payment_term_name))
            if digits:
                crdays = int(digits)

        regtype = "Unregistered"
        if self.vat:
            regtype = "Regular"

        state_name = self.state_id.name if self.state_id else ""

        category_name = ""
        if self.category_id:
            category_name = self.category_id[0].name

        bank = self.bank_ids[:1]
        bank_name = bank.bank_id.name or "" if bank else ""
        bank_branch = bank.bank_id.city or "" if bank else ""
        bank_address = bank.bank_id.street or "" if bank else ""
        bank_ifsc = bank.bank_id.bic or "" if bank else ""
        bank_acc = bank.acc_number or "" if bank else ""

        contacts = self.child_ids.filtered(lambda c: c.type == 'contact')
        conper1 = contacts[0].name if contacts else ""
        conper2 = contacts[1].name if len(contacts) > 1 else ""

        acc_group_name = dict(self._fields['miracle_acc_group'].selection).get(self.miracle_acc_group) if self.miracle_acc_group else ""

        base_edit_payload = {
            "uniqueId": self.miracle_account_id,
            "accnm": self.name,
            "accalinm": self.miracle_acc_alias,
            "accgrpnm": acc_group_name,
            "panno": self.l10n_in_pan,
            "aadharno": self.miracle_aadhar_no,
            "gstin": self.vat,
            "crdays": crdays,
            "crlimit": self.credit_limit,
            "addr": {
                "conper1": conper1,
                "conper2": conper2,
                "addr1": self._split_miracle_address(self.street)[0],
                "addr2": self._split_miracle_address(self.street)[1],
                "addr3": self._split_miracle_address(self.street2)[0],
                "addr4": self._split_miracle_address(self.street2)[1],
                "citynm": self.city,
                "pincode": self.zip,
                "areanm": self.miracle_areanm,
                "statenm": state_name,
                "mob1": self.mobile,
                "mob2": self.miracle_mob2,
                "phone1": self.phone,
                "phone2": self.miracle_phone2,
                "rphone1": self.miracle_rphone1,
                "rphone2": self.miracle_rphone2,
                "email": self.email,
                "website": self.website,
                "factoryno": self.miracle_factory_no,
                "catnm": category_name,
            },
            "bankdet": {
                "bname": bank_name,
                "bbranch": bank_branch,
                "baddress": bank_address,
                "bifsc": bank_ifsc,
                "baccno": bank_acc,
            },
        }

        base_edit_payload["addr"] = {k: v for k, v in base_edit_payload["addr"].items() if v not in (False, None, "")}
        base_edit_payload["bankdet"] = {k: v for k, v in base_edit_payload["bankdet"].items() if v not in (False, None, "")}
        base_edit_payload = {k: v for k, v in base_edit_payload.items() if v not in (False, None, "")}

        add_fields = {
            "regtypedet": [
                {
                    "regtype": regtype,
                    "regappdt": fields.Date.today().strftime("%Y-%m-%d")
                }
            ]
        }

        for company in target_companies:
            try:
                target_payload = base_edit_payload.copy()
                target_payload["action"] = "E"
                response = company._action_send_account_to_miracle(target_payload)
                
                if response.get("IsError") and ("No records found" in response.get("Message", "") or response.get("ErrorCode") == "TPA003"):
                    target_payload["action"] = "A"
                    target_payload.update(add_fields)
                    response = company._action_send_account_to_miracle(target_payload)
                
                if not response.get("IsError"):
                    notifications.append({
                        "type": "success",
                        "message": f"{self.name} | {company.name}: {response.get('Message', 'Success')}",
                    })
                else:
                    notifications.append({
                        "type": "danger",
                        "message": f"{self.name} | {company.name}: {response.get('Message')}",
                    })
                    
                _logger.info("Shared Partner Sync | Partner: %s | Company: %s | Response: %s", self.name, company.name, response)

            except Exception as e:
                _logger.exception("Error while syncing partner %s to company %s", self.name, company.name)
                notifications.append({
                    "type": "danger",
                    "message": f"{self.name} | {company.name}: {str(e)}",
                })

        return notifications
                        
    def action_upload_account_to_miracle(self, from_webhook=False):

        notifications = []

        source_company = self.env.company

        if source_company.sync_to_another_companies and not source_company.sync_target_company_ids:
            return self.env.company.miracle_notification(
                "Please configure target companies for Miracle sync.",
                "danger"
            )

        for partner in self:

            # ---------------------------------------------------
            # ACTION TYPE
            # ---------------------------------------------------

            action_type = "E"

            if not partner.miracle_account_id:
                action_type = "A"

            # ---------------------------------------------------
            # BASIC VALUES
            # ---------------------------------------------------

            crdays = 0

            if partner.property_payment_term_id:

                payment_term_name = partner.property_payment_term_id.name or ""

                digits = ''.join(filter(str.isdigit, payment_term_name))

                if digits:
                    crdays = int(digits)

            regtype = "Unregistered"

            if partner.vat:
                regtype = "Regular"

            state_name = partner.state_id.name if partner.state_id else ""

            # category_name = ""

            # if partner.category_id:
            #     category_name = partner.category_id[0].name

            # ---------------------------------------------------
            # BANK DETAILS
            # ---------------------------------------------------

            bank = partner.bank_ids[:1]

            bank_name = ""
            bank_branch = ""
            bank_address = ""
            bank_ifsc = ""
            bank_acc = ""

            if bank:
                bank_name = bank.bank_id.name or ""
                bank_branch = bank.bank_id.city or ""
                bank_address = bank.bank_id.street or ""
                bank_ifsc = bank.bank_id.bic or ""
                bank_acc = bank.acc_number or ""

            # ---------------------------------------------------
            # CONTACTS
            # ---------------------------------------------------

            contacts = partner.child_ids.filtered(
                lambda c: c.type == 'contact'
            )

            conper1 = ""
            conper2 = ""

            if contacts:
                conper1 = contacts[0].name

            if len(contacts) > 1:
                conper2 = contacts[1].name

            # ---------------------------------------------------
            # PAYLOAD
            # ---------------------------------------------------

            payload = {
                "action": action_type,

                "accnm": partner.name,

                "accalinm": partner.miracle_acc_alias,

                "accgrpnm": dict(
                    partner._fields['miracle_acc_group'].selection
                ).get(partner.miracle_acc_group),

                "panno": partner.l10n_in_pan,
                "aadharno": partner.miracle_aadhar_no,
                "gstin": partner.vat,
                "crdays": crdays,
                "crlimit": partner.credit_limit,
                # "opbal": partner.miracle_opening_balance,

                "addr": {
                    "conper1": conper1,
                    "conper2": conper2,
                    "addr1": partner._split_miracle_address(partner.street)[0],
                    "addr2": partner._split_miracle_address(partner.street)[1],
                    "addr3": partner._split_miracle_address(partner.street2)[0],
                    "addr4": partner._split_miracle_address(partner.street2)[1],
                    "citynm": partner.city,
                    "pincode": partner.zip,
                    "areanm": partner.miracle_areanm,
                    "statenm": state_name,
                    "mob1": partner.mobile,
                    "mob2": partner.miracle_mob2,
                    "phone1": partner.phone,
                    "phone2": partner.miracle_phone2,
                    "rphone1": partner.miracle_rphone1,
                    "rphone2": partner.miracle_rphone2,
                    "email": partner.email,
                    "website": partner.website,
                    "factoryno": partner.miracle_factory_no,
                    # "catnm": category_name,
                },

                "bankdet": {
                    "bname": bank_name,
                    "bbranch": bank_branch,
                    "baddress": bank_address,
                    "bifsc": bank_ifsc,
                    "baccno": bank_acc,
                },
            }

            # ---------------------------------------------------
            # EDIT MODE
            # ---------------------------------------------------

            if action_type == "E":

                payload["uniqueId"] = partner.miracle_account_id

            # ---------------------------------------------------
            # ADD MODE
            # ---------------------------------------------------

            elif action_type == "A":

                payload["regtypedet"] = [
                    {
                        "regtype": regtype,
                        "regappdt": fields.Date.today().strftime("%Y-%m-%d")
                    }
                ]

            # ---------------------------------------------------
            # REMOVE EMPTY VALUES
            # ---------------------------------------------------

            payload["addr"] = {
                k: v for k, v in payload["addr"].items()
                if v not in (False, None, "")
            }

            payload["bankdet"] = {
                k: v for k, v in payload["bankdet"].items()
                if v not in (False, None, "")
            }

            payload = {
                k: v for k, v in payload.items()
                if v not in (False, None, "")
            }

            # ---------------------------------------------------
            # SOURCE COMPANY SYNC
            # ---------------------------------------------------

            if not from_webhook:
                try:
                    response = source_company._action_send_account_to_miracle(
                        payload
                    )
                    _logger.info("Partner Sync | %s | %s | %s",partner.name,source_company.name,response)

                    if response.get("IsError"):

                        notifications.append({
                            "type": "danger",
                            "message": (
                                f"{partner.name} | "
                                f"{source_company.name}: "
                                f"{response.get('Message')}"
                            ),
                        })

                        continue

                    # ---------------------------------------------------
                    # SAVE UNIQUE ID AFTER CREATE
                    # ---------------------------------------------------

                    if action_type == "A":

                        unique_id = (
                            response.get("UniqueId")
                            or response.get("uniqueId")
                        )

                        if unique_id:

                            partner.write({
                                "miracle_account_id": unique_id,
                                "is_miracle_account": True,
                            })

                    notifications.append({
                        "type": "success",
                        "message": (
                            f"{partner.name} | "
                            f"{source_company.name}: "
                            f"{response.get('Message')}"
                        ),
                    })

                except Exception as e:

                    _logger.exception(
                        "Error syncing partner to source company"
                    )

                    notifications.append({
                        "type": "danger",
                        "message": (
                            f"{partner.name} | "
                            f"{source_company.name}: {str(e)}"
                        ),
                    })

                    continue

            # ---------------------------------------------------
            # TARGET COMPANY AUTO SYNC
            # ---------------------------------------------------

            target_notifs = partner._push_to_miracle_target_companies(source_company)
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
                action['params']['next'] = build_notification(
                    index + 1
                )

            return action

        return build_notification(0)

    def action_sync_account_from_miracle(self, api_response=None):
        self.ensure_one()
        company = self.env.company

        if api_response:
            response = api_response
        else:
            payload = {
                "id": self.miracle_account_id
            }
            response = company._action_get_account_from_miracle(payload)

        if response.get("IsError"):
            return company.miracle_notification(
                "Failed To Sync Account",
                "danger"
            )

        data = response.get("DataModel")

        if not data:
            return company.miracle_notification(
                "No data found in Miracle",
                "warning"
            )

        addr = data.get("addr") or {}
        bank = data.get("bankdet") or {}
        regtype = data.get("regtypedet") or []

        state_id = False
        if addr.get("statenm"):
            state = self.env['res.country.state'].search([
                ('name', 'ilike', addr.get("statenm")),
                ('country_id.code', '=', 'IN')
            ], limit=1)
            if state:
                state_id = state.id

        gst_treatment = False
        if regtype:
            gst_map = {
                'Regular': 'regular',
                'Composition': 'composition',
                'Unregistered': 'unregistered',
                'Consumer': 'consumer',
                'Overseas': 'overseas',
                'SEZ': 'special_economic_zone',
            }
            gst_treatment = gst_map.get(regtype[0].get("regtype"))

        street = " ".join(filter(None, [
            addr.get("addr1"),
            addr.get("addr2")
        ]))

        street2 = " ".join(filter(None, [
            addr.get("addr3"),
            addr.get("addr4")
        ]))

        payment_term_id = False
        if data.get("crdays"):
            payment_term = self.env['account.payment.term'].search([
                ('name', 'ilike', str(data.get("crdays")))
            ], limit=1)

            if payment_term:
                payment_term_id = payment_term.id

        acc_group = (data.get('accgrpnm') or '').strip().lower()

        miracle_acc_group = False
        customer_rank = 0
        supplier_rank = 0

        if acc_group == 'sundry debtors':
            miracle_acc_group = 'sundry_debtors'
            customer_rank = 1

        elif acc_group == 'sundry creditors':
            miracle_acc_group = 'sundry_creditors'
            supplier_rank = 1

        vals = {
            'name': data.get("accnm"),
            'miracle_acc_alias': data.get("accalinm"),
            'miracle_acc_group': miracle_acc_group,
            'vat': data.get("gstin"),
            'l10n_in_pan': data.get("panno"),
            'miracle_aadhar_no': data.get("aadharno"),
            'credit_limit': data.get("crlimit"),
            'miracle_opening_balance': data.get("opbal"),
            'miracle_udyam_no': data.get("udyamno"),
            'miracle_udyam_type': data.get("udyamtyp"),
            'miracle_udyam_activity': data.get("udyamact"),
            'street': street,
            'street2': street2,
            'city': addr.get("citynm"),
            'zip': addr.get("pincode"),
            'state_id': state_id,
            'miracle_areanm': addr.get("areanm"),
            'mobile': addr.get("mob1"),
            'miracle_mob2': addr.get("mob2"),
            'phone': addr.get("phone1"),
            'miracle_phone2': addr.get("phone2"),
            'miracle_rphone1': addr.get("rphone1"),
            'miracle_rphone2': addr.get("rphone2"),
            'email': addr.get("email"),
            'website': addr.get("website"),
            'miracle_factory_no': addr.get("factoryno"),
            'l10n_in_gst_treatment': gst_treatment,
            'property_payment_term_id': payment_term_id,
            'customer_rank': customer_rank,
            'supplier_rank': supplier_rank,
        }

        self.write(vals)

        contacts = self.child_ids.filtered(lambda c: c.type == 'contact')

        if addr.get("conper1"):
            if contacts:
                contacts[0].write({
                    'name': addr.get("conper1"),
                    'mobile': addr.get("mob1"),
                    'phone': addr.get("phone1"),
                    'email': addr.get("email"),
                })
            else:
                self.env['res.partner'].create({
                    'parent_id': self.id,
                    'type': 'contact',
                    'name': addr.get("conper1"),
                    'mobile': addr.get("mob1"),
                    'phone': addr.get("phone1"),
                    'email': addr.get("email"),
                })

        # Re-fetch contacts just in case one was created above
        contacts = self.child_ids.filtered(lambda c: c.type == 'contact')
        
        if addr.get("conper2"):
            if len(contacts) > 1:
                contacts[1].write({
                    'name': addr.get("conper2"),
                    'mobile': addr.get("mob2"),
                    'phone': addr.get("phone2"),
                    'email': addr.get("email"),
                })
            else:
                self.env['res.partner'].create({
                    'parent_id': self.id,
                    'type': 'contact',
                    'name': addr.get("conper2"),
                    'mobile': addr.get("mob2"),
                    'phone': addr.get("phone2"),
                    'email': addr.get("email"),
                })

        bank = data.get("bankdet") or {}

        if bank.get("baccno"):

            existing_bank = self.env['res.partner.bank'].search([
                ('partner_id', '=', self.id)
            ], limit=1)

            if existing_bank:

                bank_rec = False

                if bank.get("bname"):
                    bank_rec = self.env['res.bank'].search([
                        ('name', 'ilike', bank.get("bname"))
                    ], limit=1)

                bank_vals = {
                    'acc_number': bank.get("baccno"),
                    'bank_id': bank_rec.id if bank_rec else existing_bank.bank_id.id,
                }

                existing_bank.write(bank_vals)
        
        return company.miracle_notification(
            "Account synced successfully.",
            "success"
        )

class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    miracle_iban_no = fields.Char(string="IBAN Number")