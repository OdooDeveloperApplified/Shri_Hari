{
    'name': 'Shri hari Sales',
    'version': '18.0.1.0',
    'author': 'Applified',
    'website': 'https://www.applified.in',
    'summary': 'Sales for Shri hari',
    'depends': ['base','sale','stock','sale_stock','contacts','product','app_miracle_product'],
    'data': [
        # 'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/sales_template_views.xml',
        # 'views/captured_sales_views.xml',
        'views/res_config_settings_views.xml',
        'views/product_category_views.xml',
        'views/product_pricelist_item_views.xml',

    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
