"""Field configuration for JSON parsing - data-driven approach."""
from dataclasses import dataclass
from typing import Optional, List
import re


@dataclass
class FieldDef:
    """
    Definition for a JSON field to be included in concatenated info.
    
    Attributes:
        key: JSON key name to extract
        prefix: Text prefix to add before the value
        suffix: Text suffix to add after the value
        strip_prefix: Text to strip from the start of the value
        placeholder: Value to exclude (e.g., 'placeholder')
        extract_numbers: Whether to use regex to extract numbers first
    """
    key: str
    prefix: str = ''
    suffix: str = ''
    strip_prefix: str = ''
    placeholder: Optional[str] = None
    extract_numbers: bool = False


# Standard field configuration for payment documents
FIELD_CONFIG: List[FieldDef] = [
    FieldDef(key='schet_na_oplatu', prefix='Счет на оплату №', strip_prefix='№'),
    FieldDef(key='esf', prefix='ЭСФ №', strip_prefix='№'),
    FieldDef(key='avr', prefix='Акт выполненных работ №', strip_prefix='№'),
    FieldDef(key='akt_sverki', prefix='Акт сверки ', strip_prefix='№'),
    FieldDef(key='sluzhebnaja_zapiska', prefix='Служебная записка '),
    FieldDef(key='avansovy_otchet', prefix='Авансовый отчет №', strip_prefix='№'),
    FieldDef(key='TRU'),
    FieldDef(key='letter', prefix='Письмо '),
    FieldDef(key='mediation', prefix='Медиация/Решение суда №', strip_prefix='№'),
    FieldDef(key='nakladnye', prefix='Накладные: ', extract_numbers=True),
    FieldDef(
        key='sogl_o_rastor', 
        prefix='Согл. о расторжении №', 
        strip_prefix='№',
        placeholder='placeholder', 
        extract_numbers=True
    ),
    FieldDef(key='prilozhenija', prefix='по приложению ', strip_prefix='Приложение '),
]


def process_field(data_item: dict, field: FieldDef) -> Optional[str]:
    """
    Process a single field according to its definition.
    
    Args:
        data_item: The JSON data dictionary
        field: Field definition specifying how to process
        
    Returns:
        Formatted string or None if field is empty/invalid
    """
    value = data_item.get(field.key, '')
    if not value:
        return None
    
    value = str(value).strip()
    
    # Skip placeholder values
    if field.placeholder and value == field.placeholder:
        return None
    
    # Extract numbers if required
    if field.extract_numbers:
        match = re.search(r'\d+', value)
        if not match:
            return None
        value = value[match.start():].strip()
    
    # Strip prefix if specified
    if field.strip_prefix:
        value = value.lstrip(field.strip_prefix)
    
    if not value:
        return None
    
    return f"{field.prefix}{value}{field.suffix}"


def create_concatenated_info(data_item: dict, fields: List[FieldDef] = None) -> str:
    """
    Creates a concatenated string of payment information from JSON data.
    
    Args:
        data_item: Dictionary containing payment data
        fields: Optional custom field configuration (defaults to FIELD_CONFIG)
        
    Returns:
        Comma-separated string of formatted field values
    """
    if fields is None:
        fields = FIELD_CONFIG
    
    parts = []
    
    # Special handling: payment_type and payment_objective
    payment_type = data_item.get('payment_type', '').strip()
    payment_objective = data_item.get('payment_objective', '').strip()
    
    if payment_type and payment_type != payment_objective:
        parts.append(payment_type)
    
    if payment_objective:
        parts.append(payment_objective)
    
    # Process configured fields
    for field in fields:
        result = process_field(data_item, field)
        if result:
            parts.append(result)
    
    # Special handling: zusaetzliches_vertrag / contract
    zusaetzliches_vertrag = data_item.get('zusaetzliches_vertrag', '')
    if zusaetzliches_vertrag and zusaetzliches_vertrag != 'placeholder':
        zv_text = str(zusaetzliches_vertrag).lstrip('Доп. соглашение')
        parts.append(f'ДС {zv_text}')
    else:
        name_of_contract = data_item.get('name_of_contract', '')
        date_of_contract = data_item.get('date_of_contract', '')
        if name_of_contract and date_of_contract:
            parts.append(f"Дог. {name_of_contract}")
    
    # Special handling: payment_number
    payment_number = data_item.get('payment_number', '')
    doctype = data_item.get('doctype', '')
    if payment_number:
        parts.append(f"{doctype} №{payment_number}")
    
    return ", ".join(parts).rstrip(", ")
