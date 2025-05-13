from flask import Blueprint, request, jsonify
from models.priority_registry import fill_priority_registry
from utils.file_manager import save_excel
from config import BASE_DIR
import logging

priority_registry_bp = Blueprint('priority_registry', __name__)

@priority_registry_bp.route('/form_priority_registry', methods=['POST'])
def form_priority_registry():
    try:
        json_data = request.get_json(force=True)
        object_name = json_data.get('object_name', 'Неизвестно')
        regnum = json_data.get('registry_name', 'Б/Н')

        workbook = fill_priority_registry(json_data)
        filename = save_excel(workbook, BASE_DIR, regnum, report_type="reestr_prioritetov")
        workbook.close()

        return jsonify({"download_url": f"{request.host_url}saves/{filename}"})
    except Exception as e:
        logging.error(f"Error generating priority registry report: {e}")
        return jsonify({"error": "Не удалось создать реестр предстоящих платежей"}), 500
