#!/usr/bin/env python3
"""Quick test for the refactored scripts.py"""
import sys
sys.path.insert(0, '/Users/akha/Programming/excelium')

from utils.scripts import create_concatenated_info, FIELD_CONFIG

print(f"FIELD_CONFIG has {len(FIELD_CONFIG)} entries")

# Test with sample data
test_data = {
    'payment_type': 'Аванс',
    'payment_objective': 'Test payment',
    'TRU': 'Материалы',
    'avr': 123,
    'esf': '№456',
}
result = create_concatenated_info(test_data)
print(f"Test result: {result}")

# Full integration test
print("\nRunning full integration test...")
from models.inner_registry import format_excel_inner
import json

with open('tests/model.json') as f:
    data = json.load(f)

wb = format_excel_inner(data)
print(f"Generated {len(wb.sheetnames)} sheets")
print(f"Sheets: {wb.sheetnames[:5]}...")
wb.close()
print("SUCCESS!")
