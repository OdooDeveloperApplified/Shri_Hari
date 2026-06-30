from odoo import fields, models
import logging
_logger = logging.getLogger(__name__)

class Account(models.Model):
    _inherit = 'account.account'

    miracle_account_id = fields.Char(string="Miracle Account ID",readonly=True, copy=False)
    is_miracle_account = fields.Boolean(string="Is Miracle Account",readonly=True,copy=False)
    miracle_acc_group = fields.Char(string="Miracle Account Group",readonly=True)
    miracle_sup_group = fields.Char(string="Miracle Super Group",readonly=True)

    account_code_map = {
        "Cash": {"code": "100101", "miracle_group": "Cash-in-hand"},
        "Bank": {"code": "100201", "miracle_group": "Bank Accounts (Banks)"},
        "Bank Charges": {"code": "211300", "miracle_group": "Expense Account"},
        "Bank Suspense Account": {"code": "100202", "miracle_group": "Current Assets"},
        "Outstanding Receipts": {"code": "100203", "miracle_group": "Current Assets"},
        "Outstanding Payments": {"code": "100204", "miracle_group": "Current Assets"},
        "Inventories": {"code": "100310", "miracle_group": "Stock-in-hand"},
        "SGST Receivable": {"code": "100510", "miracle_group": "Current Assets"},
        "CGST Receivable": {"code": "100520", "miracle_group": "Current Assets"},
        "IGST Receivable": {"code": "100530", "miracle_group": "Current Assets"},
        "IGST Paid on SEZ/Export Sales": {"code": "100531", "miracle_group": "Current Assets"},
        "IGST SEZ/Export Control Account": {"code": "112341", "miracle_group": "Duties & Taxes"},
        "CESS Receivable": {"code": "100550", "miracle_group": "Current Assets"},
        "Tax Receivable": {"code": "100560", "miracle_group": "Current Assets"},
        "Reverse Charge GST on Purchase": {"code": "100570", "miracle_group": "Current Assets"},
        "TDS Receivable": {"code": "100580", "miracle_group": "Current Assets"},
        "Deposit Account": {"code": "100610", "miracle_group": "Current Assets"},
        "Prepaid Insurance": {"code": "100710", "miracle_group": "Current Assets"},
        "Liquidity Transfer": {"code": "100801", "miracle_group": "Current Assets"},
        "Deferred Expenses": {"code": "100840", "miracle_group": "Current Assets"},
        "Buildings": {"code": "101100", "miracle_group": "Fixed Assets"},
        "Land": {"code": "101200", "miracle_group": "Fixed Assets"},
        "Equipment": {"code": "101300", "miracle_group": "Fixed Assets"},
        "Vehicle": {"code": "101400", "miracle_group": "Fixed Assets"},
        "Computer/Laptops (Assets)": {"code": "101500", "miracle_group": "Fixed Assets"},
        "Furniture": {"code": "101600", "miracle_group": "Fixed Assets"},
        "Air Conditionar": {"code": "101700", "miracle_group": "Fixed Assets"},
        "Misc Assets": {"code": "101800", "miracle_group": "Fixed Assets"},
        "Debtors": {"code": "100400", "miracle_group": "Sundry Debtors"},
        "Debtors (PoS)": {"code": "100410", "miracle_group": "Sundry Debtors"},
        "Tax Current Account - Receivable": {"code": "100590", "miracle_group": "Current Assets"},
        "Undistributed Profits/Losses": {"code": "999999", "miracle_group": "Partner Remuneration"},
        "Electricity Expense": {"code": "210000", "miracle_group": "Expense Account"},
        "Salary Expense": {"code": "210100", "miracle_group": "Expense Account"},
        "Office Rent": {"code": "210200", "miracle_group": "Expense Account"},
        "House Keeping Expense": {"code": "210300", "miracle_group": "Expense Account"},
        "Postage And Courier Expense": {"code": "210400", "miracle_group": "Expense Account"},
        "Internet Expense": {"code": "210500", "miracle_group": "Expense Account"},
        "Telephone Expense": {"code": "210600", "miracle_group": "Expense Account"},
        "Purchase Expense": {"code": "210700", "miracle_group": "Expense Account"},
        "Computer/Laptop Accessories": {"code": "210800", "miracle_group": "Expense Account"},
        "News Paper And Magazine": {"code": "210900", "miracle_group": "Expense Account"},
        "Business Promotion": {"code": "211000", "miracle_group": "Expense Account"},
        "Entertainment Expense": {"code": "211100", "miracle_group": "Expense Account"},
        "Professional Services": {"code": "211200", "miracle_group": "Expense Account"},
        "Diwali Bonus/Gift": {"code": "211400", "miracle_group": "Expense Account"},
        "Parts Purchase": {"code": "211500", "miracle_group": "Expense Account"},
        "Repairing Expense": {"code": "211600", "miracle_group": "Expense Account"},
        "Foreign Exchange Loss": {"code": "211700", "miracle_group": "Expense Account"},
        "Sales Commission Expense": {"code": "211810", "miracle_group": "Expense Account"},
        "Stationary Expense": {"code": "211820", "miracle_group": "Expense Account"},
        "Travelling Expense": {"code": "211830", "miracle_group": "Expense Account"},
        "Opening Stock": {"code": "212100", "miracle_group": "Expense Account"},
        "Purchase Stock": {"code": "212200", "miracle_group": "Expense Account"},
        "Closing Stock": {"code": "212300", "miracle_group": "Expense Account"},
        "Loss on Sale of Assets": {"code": "213100", "miracle_group": "Expense Account"},
        "Write Off Expense": {"code": "213200", "miracle_group": "Expense Account"},
        "Round off Expense": {"code": "213201", "miracle_group": "Expense Account"},
        "House Rent Allowance Expense": {"code": "300001", "miracle_group": "Expense Account"},
        "Other Allowance Expense": {"code": "300002", "miracle_group": "Expense Account"},
        "Bonus to Employee Expense": {"code": "300003", "miracle_group": "Expense Account"},
        "Cash Difference Loss": {"code": "999002", "miracle_group": "Expense Account"},
        "Local Sales": {"code": "200110", "miracle_group": "Income"},
        "Retail Sales": {"code": "200120", "miracle_group": "Income"},
        "Export Sales": {"code": "200130", "miracle_group": "Income"},
        "Local Services": {"code": "200210", "miracle_group": "Income"},
        "Export Services": {"code": "200220", "miracle_group": "Income"},
        "Interest Revenues": {"code": "201000", "miracle_group": "Income"},
        "Gain on Sale of Assets": {"code": "201100", "miracle_group": "Income"},
        "Write off Income": {"code": "201200", "miracle_group": "Income"},
        "Round off Income": {"code": "213202", "miracle_group": "Income"},
        "Foreign Exchange Profit": {"code": "201300", "miracle_group": "Income(Other Then Sale)"},
        "Cash Difference Gain": {"code": "999001", "miracle_group": "Income(Other Then Sale)"},
        "Deferred Income": {"code": "100850", "miracle_group": "Current Liabilities"},
        "Capital Account": {"code": "111100", "miracle_group": "Capital Account"},
        "Reserve And Surplus Account": {"code": "111200", "miracle_group": "Reserves & Surplus"},
        "Bank OD Account": {"code": "112210", "miracle_group": "Bank OCC a/c"},
        "Secured Loan Account": {"code": "112220", "miracle_group": "Secured Loans"},
        "Unsecured Loan Account": {"code": "112230", "miracle_group": "Unsecured Loans"},
        "TDS Payable": {"code": "112310", "miracle_group": "Duties & Taxes"},
        "SGST Payable": {"code": "112320", "miracle_group": "Duties & Taxes"},
        "CGST Payable": {"code": "112330", "miracle_group": "Duties & Taxes"},
        "IGST Payable": {"code": "112340", "miracle_group": "Duties & Taxes"},
        "IGST Payable - Export": {"code": "112342", "miracle_group": "Duties & Taxes"},
        "CESS Payable": {"code": "112350", "miracle_group": "Duties & Taxes"},
        "Tax Payable": {"code": "112360", "miracle_group": "Duties & Taxes"},
        "GST RCM Control Account": {"code": "112370", "miracle_group": "Duties & Taxes"},
        "Wages Payable": {"code": "112410", "miracle_group": "Duties & Taxes"},
        "Interest Payable": {"code": "112420", "miracle_group": "Duties & Taxes"},
        "Notes Payable": {"code": "112430", "miracle_group": "Duties & Taxes"},
        "TDS Deducted": {"code": "112440", "miracle_group": "Duties & Taxes"},
        "TCS Collected": {"code": "112450", "miracle_group": "Duties & Taxes"},
        "Supplementary Allowance Expense": {"code": "300004", "miracle_group": "Current Liabilities"},
        "Performance Bonus": {"code": "300005", "miracle_group": "Current Liabilities"},
        "Provident fund - Employee Payable": {"code": "300007", "miracle_group": "Current Liabilities"},
        "Provident fund - Employer Payable": {"code": "300008", "miracle_group": "Current Liabilities"},
        "Advance to Employee": {"code": "300009", "miracle_group": "Current Liabilities"},
        "Salary Exp Payable": {"code": "300010", "miracle_group": "Current Liabilities"},
        "Leave Travel Allowance Expense": {"code": "300011", "miracle_group": "Current Liabilities"},
        "Professional Tax Payable": {"code": "300012", "miracle_group": "Current Liabilities"},
        "Creditors": {"code": "112110", "miracle_group": "Sundry Creditors"},
        "Tax Current Account - Payable": {"code": "112390", "miracle_group": "Current Liabilities"},
        "Employee Reimbursement Expense": {"code": "300006", "miracle_group": "Current Liabilities"}
    }

    MIRACLE_SUPER_GROUP = {
        'Cash-in-hand': 'Current Assets',
        'Bank Accounts (Banks)': 'Current Assets',
        'Expense Account': 'Expense Account',
        'Current Assets': 'Current Assets',
        'Stock-in-hand': 'Stock-in-hand',
        'Duties & Taxes': 'Current Assets',
        'Fixed Assets': 'Fixed Assets',
        'Sundry Debtors': 'Current Assets',
        'Partner Remuneration': 'Partner Remuneration',
        'Income': 'Income',
        'Income(Other Then Sale)': 'Income',
        'Current Liabilities': 'Current Liabilities',
        'Capital Account': 'Capital Account',
        'Reserves & Surplus': 'Reserves & Surplus',
        'Bank OCC a/c': 'Loans (Liability)',
        'Secured Loans': 'Loans (Liability)',
        'Unsecured Loans': 'Loans (Liability)',
        'Sundry Creditors': 'Current Liabilities'
    }

    def _action_insert_miracle_accounts(self, account_data):
        if account_data.get("IsError"):
            return self.env.company.miracle_notification(
                account_data.get("Message"),
                "danger"
            )

        group_map = {}
        for account_name, vals in self.account_code_map.items():
            miracle_group = vals.get("miracle_group", "").strip().lower()
            group_map.setdefault(miracle_group, []).append(vals)

        api_data = account_data.get('Data', [])
        target_codes = []

        for acc in api_data:
            miracle_group_name = acc.get('accgrpnm', '').strip().lower()
            mapped_accounts = group_map.get(miracle_group_name)
            if mapped_accounts:
                for map_info in mapped_accounts:
                    target_codes.append(map_info.get('code'))

        existing_accounts = self.search([('code', 'in', target_codes)])
        accounts_by_code = {}
        
        for acc in existing_accounts:
            accounts_by_code.setdefault(acc.code, []).append(acc)

        for acc in api_data:
            miracle_id = acc.get('accid')
            miracle_group_name = acc.get('accgrpnm', '').strip().lower()

            if not miracle_id or not miracle_group_name:
                continue

            mapped_accounts = group_map.get(miracle_group_name)
            if not mapped_accounts:
                _logger.info("Mapping for group '%s' not found", miracle_group_name)
                continue

            for map_info in mapped_accounts:
                matched_code = map_info.get('code')
                miracle_group = map_info.get('miracle_group')

                accounts = accounts_by_code.get(matched_code, [])

                if accounts:
                    super_group = self.MIRACLE_SUPER_GROUP.get(miracle_group)

                    vals = {
                        'miracle_account_id': miracle_id,
                        'is_miracle_account': True,
                        'miracle_acc_group': miracle_group,
                        'miracle_sup_group': super_group
                    }

                    for account in accounts:
                        account.write(vals)

        return self.env.company.miracle_notification(
            account_data.get("Message"),
            "success"
        )

    # def _action_insert_miracle_accounts(self, account_data):
    #     if account_data.get("IsError"):
    #         _logger.error("Miracle API Error: %s", account_data.get("Message"))
    #         return self.env.company.miracle_notification(
    #             account_data.get("Message"),
    #             "danger"
    #         )

    #     api_data = account_data.get('Data', [])

    #     group_to_codes = {}
    #     for name, vals in self.account_code_map.items():
    #         group = vals.get("miracle_group")
    #         code = vals.get("code")

    #         if group not in group_to_codes:
    #             group_to_codes[group] = []

    #         group_to_codes[group].append(code)

    #     all_codes = [c for codes in group_to_codes.values() for c in codes]
    #     existing_accounts = self.search([('code', 'in', all_codes)])
    #     accounts_by_code = {}

    #     for acc in existing_accounts:
    #         accounts_by_code.setdefault(acc.code, []).append(acc)

    #     for rec in api_data:
    #         try:
    #             miracle_id = rec.get('accid')
    #             miracle_group = rec.get('accgrpnm', '').strip()

    #             if not miracle_id or not miracle_group:
    #                 _logger.info("Skipping invalid record: %s", rec)
    #                 continue

    #             codes = group_to_codes.get(miracle_group)

    #             if not codes:
    #                 _logger.info("No mapping found for group: %s", miracle_group)
    #                 continue

    #             super_group = self.MIRACLE_SUPER_GROUP.get(miracle_group)

    #             for code in codes:
    #                 accounts = accounts_by_code.get(code, [])

    #                 if not accounts:
    #                     _logger.info("No Odoo account found for code: %s", code)
    #                     continue

    #                 for account in accounts:
    #                     account.write({
    #                         'miracle_account_id': miracle_id,
    #                         'is_miracle_account': True,
    #                         'miracle_acc_group': miracle_group,
    #                         'miracle_sup_group': super_group
    #                     })

    #                     _logger.info(
    #                         "Updated → %s (Code: %s) | Group: %s | Miracle ID: %s",
    #                         account.name, code, miracle_group, miracle_id
    #                     )

    #         except Exception as e:
    #             _logger.exception("Error processing record: %s | Error: %s", rec, str(e))


    #     return self.env.company.miracle_notification(
    #         account_data.get("Message"),
    #         "success"
    #     )

    def action_upload_account_to_miracle(self):
        self.ensure_one()
        company = self.env.company

        if self.miracle_account_id:
            action_type = "E"
        else:
            action_type = "A"

        group_name = "Trading"

        if self.account_type == "asset_cash":
            group_name = "Cash Ledger A/C."
        elif self.account_type == "asset_current":
            group_name = "Trading"
        elif self.account_type == "asset_fixed":
            group_name = "Capital Account"
        elif self.account_type == "asset_receivable":
            group_name = "Sundry Debtors"
        elif self.account_type == "liability_payable":
            group_name = "Sundry Creditors"
        elif self.account_type == "expense":
            group_name = "Expense Account"
        elif self.account_type == "income":
            group_name = "Income"
        elif self.account_type == "income_other":
            group_name = "Income"
        elif self.account_type == "liability_current":
            group_name = "Capital Account"
        elif self.account_type == "equity":
            group_name = "Capital Account"

        payload = {
            'action': action_type,
            'accnm': self.name,
            'accalinm': self.code,
            'accgrpnm': group_name
        }

        if action_type == "E":
            payload['uniqueId'] = self.miracle_account_id

        request = company._action_send_account_to_miracle(payload)

        if request.get("IsError"):
            return company.miracle_notification(
                request.get("Message"),
                "danger"
            )
        
        if action_type == "A":
            unique_id = request.get("UniqueId")

            if not unique_id:
                return company.miracle_notification(
                    "Miracle did not return UniqueId",
                    "danger"
                )
            self.write({
                "miracle_account_id": unique_id,
                "is_miracle_account": True
            })

        return company.miracle_notification(
            request.get("Message"),
            "success"
        )