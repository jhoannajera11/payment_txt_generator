# -*- coding: utf-8 -*-
{
    'name': "Generador de Archivos de Pago TXT",

    'summary': """
        Genera archivos TXT para pagos a proveedores con layouts específicos 
        (Confirming, Santander, SPEI).""",

    'description': """
        Este módulo añade la funcionalidad de generar archivos de texto (.txt) para el pago masivo a proveedores.
        Se integra con las facturas de proveedor para crear pagos y exportarlos en formatos compatibles con 
        diferentes portales bancarios.
        - Agrega campos personalizados a los contactos para claves bancarias.
        - Implementa un asistente para seleccionar facturas y generar los archivos.
        - Maneja múltiples layouts y agrupa los pagos en archivos separados (Confirming y Transferencias).
    """,

    'author': "Humanytek",
    'website': "https://humanytek.com/",

    'category': 'Accounting',
    'version': '18.0.1.0.0',

    'depends': ['account'],

    'data': [
        'security/ir.model.access.csv',
        'views/payment_wizard_views.xml',
        'views/res_partner_views.xml',
    ],
    
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}