{
    'name': 'Miracle Cloud Erp Authentication',
    'version': '18.0.1.0',
    'sequence': -101,
    'author': 'Applified',
    'website': 'https://www.applified.in',
    'summary': 'Miracle Cloud Erp Authentication By Applified',
    'depends': ['base_setup','base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'data/cron.xml',
        'views/res_company.xml',
        'views/res_config_settings.xml',
        'views/miracle_token_session.xml',
        'views/miracle_api_log.xml',
        'views/menu.xml'
    ],
    'license': 'OPL-1',
    'installable': True,
    'application': True,
}
