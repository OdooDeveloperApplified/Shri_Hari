from odoo import api, fields, models
from datetime import timedelta
import secrets


class WhatsappOtp(models.Model):
    _name = 'whatsapp.otp'
    _description = 'WhatsApp Login OTP'
    _order = 'id desc'

    mobile = fields.Char(required=True, index=True)
    otp = fields.Char(required=True)
    generated_at = fields.Datetime(required=True, default=fields.Datetime.now)
    expiry_at = fields.Datetime(required=True)
    attempts = fields.Integer(default=0)
    verified_at = fields.Datetime()

    @api.model
    def has_recent_request(self, mobile, cooldown_seconds):
        """True if an OTP was already generated for this number within the
        cooldown window - blocks resend spam (and wasted WhatsApp sends)."""
        cutoff = fields.Datetime.now() - timedelta(seconds=cooldown_seconds)
        return bool(self.search_count([
            ('mobile', '=', mobile),
            ('generated_at', '>=', cutoff),
        ]))

    @api.model
    def generate_for_mobile(self, mobile, length=6, expiry_minutes=10, code=None):
        """Create a new OTP row for `mobile` and return the record (not
        just the code) - callers need the record so a failed WhatsApp send
        can unlink it rather than leaving a valid, never-delivered code
        sitting in the database.

        `code`, when given, is used as-is instead of generating a random
        one - the store-review bypass's one use case, so a reviewer always
        gets the same fixed OTP.
        """
        code = code or ''.join(str(secrets.randbelow(10)) for _ in range(length))
        return self.create({
            'mobile': mobile,
            'otp': code,
            'generated_at': fields.Datetime.now(),
            'expiry_at': fields.Datetime.now() + timedelta(minutes=expiry_minutes),
        })

    @api.model
    def verify(self, mobile, code, max_attempts=5):
        """Check `code` against the latest unverified OTP for `mobile`.
        Returns (ok, message) - ok is True only for a correct match that
        is not expired, not already used, and not over the attempt limit.
        """
        otp = self.search([
            ('mobile', '=', mobile),
            ('verified_at', '=', False),
        ], order='id desc', limit=1)

        if not otp or otp.expiry_at < fields.Datetime.now():
            return False, "OTP expired, please request a new one."

        if otp.attempts >= max_attempts:
            return False, "Too many incorrect attempts, please request a new one."

        if otp.otp != code:
            otp.attempts += 1
            return False, "Incorrect OTP."

        otp.verified_at = fields.Datetime.now()
        return True, "OK"
