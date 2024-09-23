from flask import Blueprint, request, jsonify
import os
import logging
from models.outer_registry import format_excel_outer
from utils.file_manager import save_excel
from config import BASE_DIR

# Create a Blueprint for outer_registry
outer_registry_bp = Blueprint('outer_registry', __name__)

@outer_registry_bp.route('/form_outer_registry', methods=['POST'])
def form_outer_registry():
    try:
        HOST = request.host_url.lstrip('/')
        json_data = request.get_json(force=True)
        logging.info('Fetched JSON data: %s', json_data)

        # Generate the Excel workbook for the outer registry
        workbook = format_excel_outer(json_data)

        # Save the Excel file
        filename = save_excel(workbook, BASE_DIR, report_type="vneshny_reestr")
        workbook.close()

        # Construct download URL
        download_url = f"{HOST}saves/{filename}"
        return jsonify({"download_url": download_url})

    except Exception as e:
        logging.error(f"Error generating outer registry report: {e}")
        return jsonify({"error": "Failed to generate outer registry report"}), 500