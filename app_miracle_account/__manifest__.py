{
    'name': 'Miracle Cloud Erp Account Manage',
    'version': '18.0.1.0',
    'sequence': -103,
    'author': 'Applified',
    'website': 'https://www.applified.in',
    'summary': 'Miracle Cloud ERP Account Manage By Applified',
    'depends': ['base','contacts','app_miracle_auth','account','base_accounting_kit','app_miracle_product'],
    'data': [
        # 'security/ir.model.access.csv',
        'views/res_company.xml',
        'views/res_config_settings.xml',
        'views/res_partner.xml',
        'views/res_partner_bank_views.xml',
        'views/account_account_views.xml'
        # 'views/menu.xml'
    ],
    'license': 'OPL-1',
    'installable': True,
    'application': True,
}
