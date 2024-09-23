from flask import Blueprint, request, jsonify
import os
import logging
from models.inner_registry import format_excel_inner
from utils.file_manager import save_excel
from config import BASE_DIR  # Import BASE_DIR from config

# Create a Blueprint for inner_registry
inner_registry_bp = Blueprint('inner_registry', __name__)

@inner_registry_bp.route('/form_inner_registry', methods=['POST'])
def form_inner_registry():
    try:
        json_data = request.get_json(force=True)
        HOST = request.host_url.lstrip('/')
        # Assume `request` contains payment documents
        payment_documents = json_data.get('request', [])
        regnum = payment_documents[0].get('registry_name', '').strip('РЕЕСТР ПЛАТЕЖЕЙ №')

        # Sort payment documents by object_name
        sorted_payment_documents = sorted(payment_documents, key=lambda x: x.get('object_name', ''))
        json_data = {'request': sorted_payment_documents}

        logging.info('Fetched JSON data: %s', json_data)

        # Process the received JSON data into an Excel workbook
        workbook = format_excel_inner(json_data)

        # Save the Excel file
        filename = save_excel(workbook, BASE_DIR, regnum, report_type="reestr")
        workbook.close()

        # Construct download URL
        download_url = f"{HOST}saves/{filename}"
        return jsonify({"download_url": download_url})

    except Exception as e:
        logging.error(f"Error generating inner registry report: {e}")
        return jsonify({"error": "Failed to generate inner registry report"}), 500