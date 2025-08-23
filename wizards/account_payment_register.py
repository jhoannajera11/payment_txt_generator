# -*- coding: utf-8 -*-

import base64
import io
import zipfile
from datetime import datetime

from odoo import models, api, _
from odoo.exceptions import UserError

class AccountPaymentRegister(models.TransientModel):
    _inherit = 'account.payment.register'

    # --- El diccionario de bancos y las funciones de formato no cambian ---
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
        return (text or '').ljust(length)

    def _pad_left_zeros(self, number, length):
        return str(number).zfill(length)

    def _get_partner_bank_info(self, partner):
        bank_account = partner.bank_ids.filtered(lambda b: b.active)[:1]
        if not bank_account:
            raise UserError(_("El proveedor '%s' no tiene una cuenta bancaria activa configurada.") % partner.name)
        return bank_account, bank_account.bank_id

    def _format_confirming_line(self, payment):
        partner = payment.partner_id
        sequence = partner.x_confirming_sequence
        partner.x_confirming_sequence += 1
        fields = ['1', self._pad_right(partner.x_confirming_key, 20), '001', self._pad_left_zeros(sequence, 8), self._pad_left_zeros(int(payment.amount * 100), 21), datetime.now().strftime('%d%m%Y'), datetime.now().strftime('%d%m%Y')]
        return ''.join(fields)

    def _format_santander_line(self, payment):
        partner = payment.partner_id
        bank_account, _ = self._get_partner_bank_info(partner)
        fields = ['LTX07', self._pad_right('65501571237', 18), self._pad_right(bank_account.acc_number, 20), self._pad_left_zeros(int(payment.amount * 100), 18), self._pad_right(partner.x_spei_reference, 40), datetime.now().strftime('%d%m%Y'), self._pad_right(partner.email, 40)]
        return ''.join(fields)

    def _format_spei_line(self, payment):
        """Genera una línea para el archivo de Transferencias SPEI (Layout 3)."""
        partner = payment.partner_id
        bank_account, bank = self._get_partner_bank_info(partner)
        
        bank_code_str = self.BANK_CODE_MAP.get((bank.name or '').upper(), '')
        if len(bank_code_str) == 4:
            bank_code_str = self._pad_right(bank_code_str, 5)

        # La cuenta CLABE ahora viene del campo específico de la localización mexicana
        clabe_account = bank_account.l10n_mx_edi_clabe or bank_account.acc_number
        if not clabe_account:
             raise UserError(_("La cuenta bancaria del proveedor '%s' no tiene un número de cuenta o CLABE configurado.") % partner.name)

        fields = [
            'LTX05',  # <-- CAMBIO 1: Código de Layout corregido a LTX05.
            self._pad_right('65501571237', 18),
            self._pad_right(clabe_account, 20),  # <-- CAMBIO 2: Se usa el campo de la CLABE.
            self._pad_right(bank_code_str, 5),
            self._pad_right(partner.name, 40),
            '0100',
            self._pad_left_zeros(int(payment.amount * 100), 18),
            '01001',
            self._pad_right(partner.x_spei_reference, 40),
            ' ' * 7,
            self._pad_right(partner.email, 40),
            '1',
            ' ' * 8,
        ]
        return ''.join(fields)

    def action_create_payments_and_generate_file(self):
        payments_to_process = self._create_payments()

        if not payments_to_process:
            return {'type': 'ir.actions.act_window_close'}
        
        confirming_payments = payments_to_process.filtered(lambda p: p.partner_id.x_confirming_key)
        transfer_payments = payments_to_process - confirming_payments
        
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
            return {'type': 'ir.actions.act_window_close'}

        if len(generated_files) == 1:
            filename, content = list(generated_files.items())[0]
            file_data = base64.b64encode(content.encode('utf-8'))
        else:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
                for filename, content in generated_files.items():
                    zf.writestr(filename, content)
            filename = 'paquete_de_pagos.zip'
            file_data = base64.b64encode(zip_buffer.getvalue())

        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': file_data,
            'type': 'binary',
            'res_model': self._name,
            'res_id': self.id,
        })
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }