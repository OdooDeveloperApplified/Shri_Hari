{
    'name': 'App User Access Management',
    'version': '18.0.1.0.0',
    'category': 'Administration',
    'summary': 'Custom wizard to grant App (Internal User) access using Mobile login.',
    'description': """
        This module provides a custom wizard on the Contact (res.partner) model 
        to easily create Internal Users for the mobile app, using the contact's 
        mobile number as their login.
    """,
    'author': 'Shree Hari',
    'depends': ['base', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/wizard_app_access_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
