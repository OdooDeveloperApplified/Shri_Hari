# WhatsApp OTP login — design

Replaces the mobile app's password-based `/user_login` with OTP delivered
over WhatsApp. Odoo's own backend login (staff/admin, native `res.users`
password auth) is untouched — this only changes how the mobile app
authenticates customers/dealers.

**Assumption, confirm before building:** OTP is a *login* mechanism for
numbers that already exist as a registered contact/user — not a public
self-signup flow. `/request_otp` rejects unregistered numbers up front
rather than sending a code that could never successfully verify.

---

## 1. Where this lives

Inside the existing `shrihari_api` module — no new module. This isn't a
sync-with-an-external-system problem the way Miracle is (no inbound
direction, no product/account/voucher split needed); it's "the mobile API
layer gains two endpoints and one small supporting model."

## 2. New / changed files

| File | Change |
|---|---|
| `shrihari_api/models/whatsapp_otp.py` | **New.** The `whatsapp.otp` model. |
| `shrihari_api/models/res_company.py` | **Extend.** New WhatsApp config fields + `_send_whatsapp_otp()`. |
| `shrihari_api/controllers/otp.py` | **New.** `/request_otp` and `/verify_otp`. |
| `shrihari_api/security/ir.model.access.csv` | **Extend.** Access rule for `whatsapp.otp`. |
| `shrihari_api/__manifest__.py` | **Extend.** Register the new files. |
| `shrihari_api/controllers/user.py` | **Unchanged for now.** `/user_login` stays in place, unused by the app, as a fallback — not deleted until OTP has proven itself in production. |

## 3. The `whatsapp.otp` model

| Field | Purpose |
|---|---|
| `mobile` | Number the code was sent to |
| `otp_hash` | The code, hashed — never stored in plain text |
| `generated_at` | When this code was issued |
| `expiry_at` | Short window — 2-5 minutes |
| `attempts` | Wrong-guess counter, caps brute-forcing |
| `verified_at` | Null until successfully used — blocks replay of an already-used code |

No backend UI view needed — nobody browses this day to day, it's purely
data the two endpoints read and write.

## 4. Company config fields (`res_company.py`)

Same convention as the existing Miracle fields in this file — stored as
configurable fields, not hardcoded strings:

- `whatsapp_api_domain` — e.g. `https://crm.ihakimi.com`
- `whatsapp_api_version` — the Meta Graph API version segment
- `whatsapp_phone_number_id` — which WhatsApp number sends the OTP
- `whatsapp_access_token`
- `whatsapp_otp_template_name` — `shreehari_otp`
- `whatsapp_otp_template_lang` — `en`

Plus one method, **`_send_whatsapp_otp(self, mobile, otp_code)`** — the
single choke-point every OTP send goes through, mirroring
`miracle_api_call()`: builds the template payload below, posts it, and
logs the attempt so "did the OTP actually send" is always answerable from
a log, not a guess.

### Exact template payload this method builds

The approved template (`shreehari_otp`, Authentication category) has a
Copy Code button, which means the *same* OTP value is required in two
places — the body, and the button parameter:

```json
{
    "messaging_product": "whatsapp",
    "to": "919876543210",
    "recipient_type": "individual",
    "type": "template",
    "template": {
        "language": { "policy": "deterministic", "code": "en" },
        "name": "shreehari_otp",
        "components": [
            {
                "type": "body",
                "parameters": [{ "type": "text", "text": "482913" }]
            },
            {
                "type": "button",
                "sub_type": "url",
                "index": 0,
                "parameters": [{ "type": "text", "text": "482913" }]
            }
        ]
    }
}
```

Sent to `POST {whatsapp_api_domain}/api/meta/{whatsapp_api_version}/{whatsapp_phone_number_id}/messages`
with `Authorization: Bearer {whatsapp_access_token}`.

## 5. `POST /request_otp`

1. App sends `{ "mobile": "..." }`.
2. Look up the matching `res.users` — **reuse the exact phone-matching
   logic already in `/user_login`** (last-10-digit smart match), not new
   code.
3. Not found → reject: "This mobile number is not registered."
4. Cooldown check — an unexpired `whatsapp.otp` row already created for
   this number in the last N seconds? Reject: "Please wait before
   requesting another code." (Stops spam and wasted WhatsApp sends.)
5. Generate a random numeric code, hash it, create the `whatsapp.otp` row
   with a short expiry.
6. `company._send_whatsapp_otp(mobile, otp_code)`.
7. Respond `{"success": true, "message": "OTP sent"}` — the code itself
   never appears in the response.

## 6. `POST /verify_otp`

1. App sends `{ "mobile": "...", "otp": "..." }`.
2. Find the most recent, unexpired, unverified `whatsapp.otp` row for that
   number.
3. None / expired → "OTP expired, request a new one."
4. `attempts` already at the limit (e.g. 5) → "Too many incorrect
   attempts, request a new one." (Caps brute-forcing a 4-6 digit code.)
5. Hash the submitted code, compare to `otp_hash`.
   - Mismatch → increment `attempts`, return "Incorrect OTP."
   - Match → set `verified_at`, look up the user again, **issue a
     `partner.api.key` token exactly the way `/user_login` does today** —
     same creation/reuse logic, same response shape (`user_id`, `name`,
     `email`, `access_token`, `customer {...}`).

The app's existing "login succeeded" handling doesn't need to change —
OTP is just a second front door into the same token system.

## 7. What's deliberately reused, not reinvented

- Phone-number matching → same logic as `/user_login`.
- Token issuance → same `partner.api.key` create/reuse logic as `/user_login`.
- Centralized external call + logging → same pattern as `miracle_api_call()`.

## 8. Open decisions

- [ ] Confirm the "existing users only" assumption in the header above.
- [ ] OTP length (4 vs 6 digits) and expiry window.
- [ ] Resend cooldown duration.
- [ ] Max wrong-attempt count before requiring a fresh OTP.
- [ ] When to formally retire `/user_login` once OTP is live.
