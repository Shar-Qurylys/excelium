import unittest
from scripts import create_concatenated_info

# Assuming the create_concatenated_info function is defined in a module named 'payment_info'
# from payment_info import create_concatenated_info

class TestCreateConcatenatedInfo(unittest.TestCase):
    def test_all_fields_empty(self):
        data_item = {}
        result = create_concatenated_info(data_item)
        self.assertEqual(result, '')

    def test_missing_payment_type(self):
        data_item = {
            'payment_objective': 'Objective',
            'schet_na_oplatu': '123',
            'esf': '456'
        }
        result = create_concatenated_info(data_item)
        self.assertEqual(result, 'Objective, Счет на оплату №123, ЭСФ №456')

    def test_missing_payment_objective(self):
        data_item = {
            'payment_type': 'Type',
            'schet_na_oplatu': '123',
            'esf': '456'
        }
        result = create_concatenated_info(data_item)
        self.assertEqual(result, 'Type, Счет на оплату №123, ЭСФ №456')

    def test_missing_schet_na_oplatu(self):
        data_item = {
            'payment_type': 'Type',
            'payment_objective': 'Objective',
            'esf': '456'
        }
        result = create_concatenated_info(data_item)
        self.assertEqual(result, 'Type, Objective, ЭСФ №456')

    def test_missing_esf(self):
        data_item = {
            'payment_type': 'Objective',
            'payment_objective': 'Objective',
            'schet_na_oplatu': '123'
        }
        result = create_concatenated_info(data_item)
        self.assertEqual(result, 'Objective, Счет на оплату №123')

    def test_missing_all_non_required_fields(self):
        data_item = {
            'payment_type': 'Type',
            'payment_objective': 'Objective',
            'schet_na_oplatu': '',
            'esf': '',
            'avr': '',
            'akt_sverki': '',
            'sluzhebnaja_zapiska': '',
            'avansovy_otchet': '',
            'TRU': '',
            'letter': '',
            'mediation': '',
            'nakladnye': '123',
            'sogl_o_rastor': '',
            'prilozhenija': '',
            'zusaetzliches_vertrag': '',
            'name_of_contract': '',
            'payment_number': '',
            'doctype': ''
        }
        result = create_concatenated_info(data_item)
        self.assertEqual(result, 'Type, Objective, Накладные: 123')

    def test_all_fields_present(self):
        data_item = {
            'payment_type': 'Type',
            'payment_objective': 'Objective',
            'schet_na_oplatu': '123',
            'esf': '456',
            'avr': '789',
            'akt_sverki': '111',
            'sluzhebnaja_zapiska': '222',
            'avansovy_otchet': '333',
            'TRU': 'TRU description',
            'letter': 'Letter content',
            'mediation': '444',
            'nakladnye': '',
            'sogl_o_rastor': '666',
            'prilozhenija': 'Приложение 2',
            'zusaetzliches_vertrag': 'Additional agreement',
            'name_of_contract': 'Contract name',
            'payment_number': '777',
            'doctype': 'Invoice'
        }
        result = create_concatenated_info(data_item)
        self.assertEqual(result, (
            'Type, Objective, Счет на оплату №123, ЭСФ №456, Акт выполненных работ №789, '
            'Акт сверки 111, Служебная записка 222, Авансовый отчет №333, TRU description, '
            'Письмо Letter content, Медиация/Решение суда №444, '
            'Согл. о расторжении №666, по приложению 2, ДС Additional agreement, '
            'Invoice №777'
        ))

if __name__ == '__main__':
    unittest.main()
