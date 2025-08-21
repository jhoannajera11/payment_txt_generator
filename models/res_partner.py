# -*- coding: utf-8 -*-

from odoo import models, fields

class ResPartner(models.Model):
    """
    Se extiende el modelo res.partner para añadir campos necesarios para la generación
    de archivos de pago bancario.
    """
    _inherit = 'res.partner'

    # --- Campos para Layout 1 (Confirming) ---
    
    x_confirming_key = fields.Char(
        string="Clave del Proveedor (Confirming)",
        help="Clave específica del proveedor utilizada para el layout de pago tipo 'Confirming'."
    )
    
    x_confirming_sequence = fields.Integer(
        string="Siguiente Núm. Documento (Confirming)",
        default=1,
        help="Contador secuencial para el 'Número de Documento' en el layout de Confirming. Se incrementa automáticamente."
    )

    # --- Campos para Layouts 2 (Santander) y 3 (SPEI) ---
    
    x_spei_reference = fields.Char(
        string="Referencia (SPEI)",
        help="Referencia numérica o alfanumérica utilizada en el concepto de pago para transferencias SPEI o de Santander."
    )