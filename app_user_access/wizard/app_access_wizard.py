from odoo import api, fields, models, Command
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class AppAccessWizard(models.TransientModel):
    _name = 'app.access.wizard'
    _description = 'Grant App Access Wizard'

    def _default_partner_ids(self):
        partner_ids = self.env.context.get('default_partner_ids', []) or self.env.context.get('active_ids', [])
        contact_ids = set()
        for partner in self.env['res.partner'].sudo().browse(partner_ids):
            # Include the partner and any contact children
            contact_partners = partner.child_ids.filtered(lambda p: p.type in ('contact', 'other')) | partner
            contact_ids |= set(contact_partners.ids)

        return [Command.link(contact_id) for contact_id in contact_ids]

    partner_ids = fields.Many2many('res.partner', string='Partners', default=_default_partner_ids)
    user_ids = fields.One2many('app.access.wizard.user', 'wizard_id', string='Users', compute='_compute_user_ids', store=True, readonly=False)

    @api.depends('partner_ids')
    def _compute_user_ids(self):
        for wizard in self:
            wizard.user_ids = [
                Command.create({
                    'partner_id': partner.id,
                    'mobile': partner.mobile,
                    # 'password': 'Welcome123!', # <--- Add this line!
                })
                for partner in wizard.partner_ids
            ]

    @api.model
    def action_open_wizard(self):
        wizard = self.create({})
        return wizard._action_open_modal()

    def _action_open_modal(self):
        return {
            'name': 'Grant App Access',
            'type': 'ir.actions.act_window',
            'res_model': 'app.access.wizard',
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }


class AppAccessWizardUser(models.TransientModel):
    _name = 'app.access.wizard.user'
    _description = 'App Access Wizard User Config'

    wizard_id = fields.Many2one('app.access.wizard', string='Wizard', required=True, ondelete='cascade')
    partner_id = fields.Many2one('res.partner', string='Contact', required=True, readonly=True, ondelete='cascade')
    mobile = fields.Char('Mobile')
    password = fields.Char('Password')

    user_id = fields.Many2one('res.users', string='User', compute='_compute_user_id', compute_sudo=True)
    is_internal = fields.Boolean('Is Internal', compute='_compute_group_details')
    mobile_state = fields.Selection([
        ('ok', 'Valid'),
        ('ko', 'Missing'),
        ('exist', 'Already Registered')
    ], string='Status', compute='_compute_mobile_state', default='ok')

    @api.depends('mobile')
    def _compute_mobile_state(self):
        existing_users = self.env['res.users'].with_context(active_test=False).sudo().search_read(
            self._get_similar_users_domain(),
            self._get_similar_users_fields()
        )
        
        for wizard_user in self:
            if not wizard_user.mobile:
                wizard_user.mobile_state = 'ko'
                continue
                
            # Clean mobile for comparison just in case
            mobile_cleaned = ''.join(filter(str.isdigit, wizard_user.mobile))
            
            is_exist = False
            for user in existing_users:
                # If there's already a user with this login/mobile who is NOT the current partner's linked user
                if self._is_mobile_similar_to_user(user, wizard_user):
                    is_exist = True
                    break
                    
            if is_exist:
                wizard_user.mobile_state = 'exist'
            else:
                wizard_user.mobile_state = 'ok'

    def _get_similar_users_domain(self):
        mobiles = [u.mobile for u in self if u.mobile]
        if not mobiles:
            return [('id', '=', -1)] 
            
        domain = ['|'] * (len(mobiles) * 2 - 1) if len(mobiles) > 0 else []
        for mobile in mobiles:
            digits_only = ''.join(filter(str.isdigit, mobile))
            if len(digits_only) >= 10:
                phone_pattern = '%' + '%'.join(list(digits_only[-10:])) + '%'
                domain.extend(['|', ('login', '=like', phone_pattern), ('mobile', '=like', phone_pattern)])
            else:
                domain.extend(['|', ('login', '=', mobile), ('mobile', '=', mobile)])
                
        # Remove extra ORs from the start if we built it that way
        while len(domain) > 1 and domain[0] == '|' and domain[1] == '|':
            domain.pop(0)
            
        return domain

    def _get_similar_users_fields(self):
        return ['id', 'login', 'mobile']

    def _is_mobile_similar_to_user(self, user_dict, wizard_user):
        if not wizard_user.mobile:
            return False
            
        user_login = user_dict.get('login') or ""
        user_mobile = user_dict.get('mobile') or ""
        
        wizard_digits = ''.join(filter(str.isdigit, wizard_user.mobile))
        
        match = False
        if len(wizard_digits) >= 10:
            last_10 = wizard_digits[-10:]
            user_login_digits = ''.join(filter(str.isdigit, user_login))
            user_mobile_digits = ''.join(filter(str.isdigit, user_mobile))
            
            if (len(user_login_digits) >= 10 and user_login_digits[-10:] == last_10) or \
               (len(user_mobile_digits) >= 10 and user_mobile_digits[-10:] == last_10):
                match = True
        else:
            match = (user_login == wizard_user.mobile or user_mobile == wizard_user.mobile)
        
        return match and user_dict['id'] != wizard_user.user_id.id

    @api.depends('partner_id')
    def _compute_user_id(self):
        for wizard_user in self:
            # Get the first active or inactive user linked to this partner
            user = wizard_user.partner_id.with_context(active_test=False).user_ids
            wizard_user.user_id = user[0] if user else False

    @api.depends('user_id', 'user_id.groups_id')
    def _compute_group_details(self):
        for wizard_user in self:
            user = wizard_user.user_id
            if user and user.has_group('base.group_user'):
                wizard_user.is_internal = True
            else:
                wizard_user.is_internal = False

    def _normalize_mobile_for_login(self, mobile):
        if not mobile:
            return False
        # Extract only digits and take the last 10 digits to ignore country codes
        digits = ''.join(c for c in mobile if c.isdigit())
        if len(digits) >= 10:
            return digits[-10:]
        return digits

    def action_grant_access(self):
        self.ensure_one()
        
        if self.mobile_state == 'ko':
            raise UserError(f'The contact "{self.partner_id.name}" does not have a valid mobile number.')
        if self.mobile_state == 'exist':
            raise UserError(f'The mobile number for "{self.partner_id.name}" is already taken by another user.')
            
        if self.is_internal:
            raise UserError(f'The partner "{self.partner_id.name}" already has internal app access.')

        if not self.password:
            raise UserError(f'Please enter a password for "{self.partner_id.name}".')

        # Save back the mobile to partner if changed
        if self.mobile and self.partner_id.mobile != self.mobile:
            self.partner_id.write({'mobile': self.mobile})

        user_sudo = self.user_id.sudo()
        group_user = self.env.ref('base.group_user')

        normalized_login = self._normalize_mobile_for_login(self.mobile)

        if not user_sudo:
            # create a new user
            company = self.partner_id.company_id or self.env.company
            user_sudo = self.env['res.users'].sudo().with_company(company.id).with_context(no_reset_password=True).create({
                'name': self.partner_id.name,
                'login': normalized_login,
                'password': self.password,
                'partner_id': self.partner_id.id,
                'company_id': company.id,
                'company_ids': [(6, 0, company.ids)],
                'groups_id': [(6, 0, [group_user.id])],
            })
        else:
            # Ensure the user has the internal group and set the password
            user_sudo.write({
                'active': True,
                'groups_id': [(4, group_user.id)],
                'password': self.password
            })
            
            # If their login was something else, and we want it to be mobile now
            if user_sudo.login != normalized_login:
                user_sudo.write({'login': normalized_login})

        return self.action_refresh_modal()

    def action_revoke_access(self):
        self.ensure_one()
        if not self.is_internal:
            raise UserError(f'The partner "{self.partner_id.name}" is not an internal user.')

        user_sudo = self.user_id.sudo()
        group_user = self.env.ref('base.group_user')

        if user_sudo:
            new_login = f"{user_sudo.login}-revoked-{fields.Datetime.now().strftime('%Y%m%d%H%M%S')}"
            user_sudo.write({
                'groups_id': [(3, group_user.id)],
                'active': False,
                'login': new_login
            })

        return self.action_refresh_modal()

    def action_refresh_modal(self):
        return self.wizard_id._action_open_modal()
