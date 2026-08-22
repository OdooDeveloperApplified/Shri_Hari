{
    'name': 'App Management',
    'version': '1.0',
    'summary': 'Manage App Versions',
    'category': 'Tools',
    'author': 'Custom',
    'depends': ['base'],
    'data': [
        'security/ir.model.access.csv',
        'views/app_version_views.xml',
    ],
    'installable': True,
    'application': True,
}