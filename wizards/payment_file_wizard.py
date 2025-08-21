# -*- coding: utf-8 -*-

import base64
import io
import zipfile
from datetime import datetime

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class PaymentFileWizard(models.TransientModel):
    _name = 'payment.file.wizard'
    _description = 'Asistente para Generar Archivos de Pago Bancario'

    # --- Campos del Asistente ---
    journal_id = fields.Many2one(
        'account.journal',
        string="Diario de Pago",
        domain="[('type', '=', 'bank')]",
        required=True,
        help="Selecciona la cuenta bancaria desde la cual se realizarán los pagos."
    )
    move_ids = fields.Many2many('account.move', string="Facturas a Pagar")

    # --- Campos para el resultado (descarga) ---
    file_data = fields.Binary("Archivo Generado", readonly=True)
    file_name = fields.Char("Nombre del Archivo", readonly=True)

    # Diccionario de Bancos para Layout SPEI
    BANK_CODE_MAP = {
        'BANXICO': 'BANCO', 'BANCOMEXT': 'BCEXT', 'BANOBRAS': 'BOBRA', 'BANJERCITO': 'BEJER',
        'NACIONAL FINANCIERA': 'NAFIN', 'BANCO DEL BIENESTAR': 'BANSE', 'HIPOTECARIA FEDERAL': 'HIFED',
        'BANAMEX': 'BANAM', 'BBVA BANCOMER': 'BACOM', 'BANCO SANTANDER': 'BANME',
        'HSBC': 'BITAL', 'BAJIO': 'BAJIO', 'INBURSA': 'BINBU', 'SCOTIA BANK': 'COMER',
        'BANREGIO': 'BANRE', 'INVEX': 'BINVE', 'BANSI': 'BANSI', 'AFIRME': 'BAFIR',
        'BANORTE/IXE': 'BBANO', 'ACCENDO BANCO': 'ABNBA', 'AMERICAN EXPRESS': 'AMEX',
        'BANK OF AMERICA': 'BAMSA', 'MUFG BANK MEXICO': 'TOKYO', 'JP MORGAN': 'CHASE',
        'BANCO MONEX': 'CMCA', 'VE POR MAS': 'DRESD', 'CITI MEXICO': 'DEUTB',
        'CREDIT SUISSE': 'CRESU', 'AZTECA': 'BAZTE', 'BANCO AUTOFIN': 'BAUTO',
        'BARCLAYS BANK': 'BARCL', 'BANCO COMPARTAMOS': 'BCOMP', 'BANCO MULTIVA': 'MULTI',
        'ACTINVER': 'PRUDE', 'INTERCAM BANCO': 'REGIO', 'BANCOPPEL': 'COPEL',
        'ABC CAPITAL': 'AMIGO', 'CONSUBANCO': 'FACIL', 'VOLKSWAGEN BANK': 'VOLKS',
        'CI BANCO': 'CONSU', 'BBASE': 'BBASE', 'BANKAOOL': 'AGROF', 'PAGATODO': 'PTODO',
        'INMOBILIARIO': 'INMOB', 'DONDE': 'DONDE', 'BANCREA': 'BCREA', 'BANCO FINTERRA': 'FINTE',
        'ICBC': 'ICBCH', 'SABADELL': 'SABAD', 'SHINAN': 'SHINH', 'MIZUHO BANK': 'MISUO',
        'BANCO S3': 'BCOS3', 'MONEX CASA DE BOLSA': '90600', 'GBM CASA DE BOLSA': '90601',
        'MASARI CASA DE BOLSA': '90602', 'VALUE CASA DE BOLSA': '90605', 'ESTRUCTURADORES': '90606',
        'VECTOR CASA DE BOLSA': '90608', 'MULTIVA CBOLSA': '90613', 'FINAMEX': '90616',
        'VALMEX': '90617', 'PROFUTURO GNP AFORE': '90620', 'SKANDIA VIDA': '90623',
        'INTERCAM CASA DE BOLSA': '90630', 'CI BOLSA': '90631', 'FINCOMUN': '90634',
        'HDI SEGUROS': '90636', 'ORDER EXPRESS': '90637', 'AKALA': '90638',
        'REFORMA': '90642', 'STP': '90646', 'EVERCORE': '90648',
        'OSKNDIA OPERADORA': '90649', 'CREDICAPITAL': '90652', 'KUSPIT': '90653',
        'SOFIEXPRESS': '90655', 'UNAGRA': '90656', 'ASP INTEGRA OPC': '90659',
        'LIBERTAD': '90670', 'CAJA POP MEXICANA': '90677', 'CRISTOBAL COLON': '90680',
        'CAJA TELEFONIST': '90683', 'TRANSFER': '90684', 'FONDO FIRA': '90685',
        'INVERCAP': '90686', 'FOMPED': '90689', 'CLS BANK': 'CLSB', 'INDEVAL': '90902',
        'CODI VALIDA': '90903'
    }

    def _pad_right(self, text, length):
        """Rellena un texto con espacios a la derecha."""
        return (text or '').ljust(length)

    def _pad_left_zeros(self, number, length):
        """Rellena un número con ceros a la izquierda."""
        return str(number).zfill(length)

    def _get_partner_bank_info(self, partner):
        """Obtiene la cuenta bancaria y el banco del proveedor."""
        bank_account = partner.bank_ids.filtered(lambda b: b.active)[:1]
        if not bank_account:
            raise UserError(_("El proveedor '%s' no tiene una cuenta bancaria activa configurada.") % partner.name)
        return bank_account, bank_account.bank_id

    def _format_confirming_line(self, payment):
        """Genera una línea para el archivo de Confirming (Layout 1)."""
        partner = payment.partner_id
        # Lee y actualiza el secuencial
        sequence = partner.x_confirming_sequence
        partner.x_confirming_sequence += 1

        fields = [
            '1', # Clave de Registro
            self._pad_right(partner.x_confirming_key, 20), # Clave del Proveedor
            '001', # Clave de Tipo de Documento
            self._pad_left_zeros(sequence, 8), # Número de Documento
            self._pad_left_zeros(int(payment.amount * 100), 21), # Importe
            datetime.now().strftime('%d%m%Y'), # Fecha de Emisión
            datetime.now().strftime('%d%m%Y'), # Fecha de Vencimiento
        ]
        return ''.join(fields)

    def _format_santander_line(self, payment):
        """Genera una línea para el archivo de Transferencias Santander (Layout 2)."""
        partner = payment.partner_id
        bank_account, _ = self._get_partner_bank_info(partner)

        fields = [
            'LTX07', # Código Layout
            self._pad_right('65501571237', 18), # Cuenta de Cargo
            self._pad_right(bank_account.acc_number, 20), # Cuenta de Abono
            self._pad_left_zeros(int(payment.amount * 100), 18), # Importe
            self._pad_right(partner.x_spei_reference, 40), # Concepto
            datetime.now().strftime('%d%m%Y'), # Fecha de Aplicación
            self._pad_right(partner.email, 40), # Email Beneficiario
        ]
        return ''.join(fields)

    def _format_spei_line(self, payment):
        """Genera una línea para el archivo de Transferencias SPEI (Layout 3)."""
        partner = payment.partner_id
        bank_account, bank = self._get_partner_bank_info(partner)
        
        bank_code_str = self.BANK_CODE_MAP.get(bank.name.upper(), '')
        if len(bank_code_str) == 4:
            bank_code_str = self._pad_right(bank_code_str, 5)

        fields = [
            'LTX07', # Código Layout
            self._pad_right('65501571237', 18), # Cuenta de Cargo
            self._pad_right(bank_account.acc_number, 20), # Cuenta de Abono
            self._pad_right(bank_code_str, 5), # Banco Receptor
            self._pad_right(partner.name, 40), # Beneficiario
            '0100', # Sucursal
            self._pad_left_zeros(int(payment.amount * 100), 18), # Importe
            '01001', # Plaza Banxico
            self._pad_right(partner.x_spei_reference, 40), # Concepto
            ' ' * 7, # Referencia Ordenante
            self._pad_right(partner.email, 40), # Email Beneficiario
            '1', # Forma de Aplicación
            ' ' * 8, # Fecha de Aplicación
        ]
        return ''.join(fields)

    def action_generate_files(self):
        self.ensure_one()

        if not self.move_ids:
            raise UserError(_("No se ha seleccionado ninguna factura para pagar."))

        # 1. Agrupar facturas por proveedor
        partner_invoices = {}
        for move in self.move_ids:
            partner_invoices.setdefault(move.partner_id, self.env['account.move'])
            partner_invoices[move.partner_id] += move
        
        # 2. Crear un pago por cada proveedor
        payments_to_process = self.env['account.payment']
        for partner, invoices in partner_invoices.items():
            payment = self.env['account.payment'].create({
                'partner_id': partner.id,
                'amount': sum(invoices.mapped('amount_residual')),
                'date': fields.Date.today(),
                'journal_id': self.journal_id.id,
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'reconciled_invoice_ids': [(6, 0, invoices.ids)],
            })
            payments_to_process += payment
        
        # 3. Agrupar pagos por tipo de layout
        confirming_payments = self.env['account.payment']
        transfer_payments = self.env['account.payment']
        
        for payment in payments_to_process:
            partner = payment.partner_id
            if partner.x_confirming_key:
                confirming_payments += payment
            else:
                transfer_payments += payment

        # 4. Generar el contenido de los archivos
        generated_files = {}
        if confirming_payments:
            lines = [self._format_confirming_line(p) for p in confirming_payments]
            generated_files['confirming.txt'] = "\n".join(lines)
        
        if transfer_payments:
            lines = []
            for payment in transfer_payments:
                _, bank = self._get_partner_bank_info(payment.partner_id)
                if bank.name and 'SANTANDER' in bank.name.upper():
                    lines.append(self._format_santander_line(payment))
                else:
                    lines.append(self._format_spei_line(payment))
            generated_files['transferencias.txt'] = "\n".join(lines)
            
        if not generated_files:
            raise UserError(_("No se pudo generar ningún archivo. Verifique la configuración de los proveedores."))

        # 5. Preparar el archivo (o archivos) para la descarga
        if len(generated_files) == 1:
            filename, content = list(generated_files.items())[0]
            self.file_name = filename
            self.file_data = base64.b64encode(content.encode('utf-8'))
        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for filename, content in generated_files.items():
                    zf.writestr(filename, content)
            self.file_name = 'paquete_de_pagos.zip'
            self.file_data = base64.b64encode(zip_buffer.getvalue())

        # 6. Devolver la vista para mostrar el enlace de descarga
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'view_mode': 'form',
            'res_id': self.id,
            'target': 'new',
        }