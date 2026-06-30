{
    'name': 'Shri hari API',
    'version': '18.0.1.0',
    'author': 'Applified',
    'website': 'https://www.applified.in',
    'summary': 'API for Shri hari',
    'depends': ['base','sale','stock','sale_stock','contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/api_access_token.xml',
    ],
    'license': 'LGPL-3',
    'installable': True,
    'application': True,
}
