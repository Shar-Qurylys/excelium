# excelium/core/__init__.py
"""Core abstractions for document generation."""

from core.document_generator import DocumentGenerator
from core.excel_generator import ExcelGenerator
from core.field_config import FieldDef, FIELD_CONFIG

__all__ = ['DocumentGenerator', 'ExcelGenerator', 'FieldDef', 'FIELD_CONFIG']
