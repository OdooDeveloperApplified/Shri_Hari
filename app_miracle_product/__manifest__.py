{
    'name': 'Miracle Cloud Erp Product Manage',
    'version': '18.0.1.0',
    'sequence': -102,
    'author': 'Applified',
    'website': 'https://www.applified.in',
    'summary': 'Miracle Cloud Erp Product Manage By Applified',
    'depends': ['app_miracle_auth','product','sale', 'sale_management', 'stock', 'purchase', 'purchase_stock'],
    'data': [
        'security/ir.model.access.csv',
        # 'data/ir_cron_data.xml',
        'views/res_company.xml',
        'views/res_config_settings.xml',
        'views/product_template.xml',
        # 'views/menu.xml'
    ],
    'license': 'OPL-1',
    'installable': True,
    'application': True,
}
