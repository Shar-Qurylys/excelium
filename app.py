from flask import Flask, send_from_directory, request, jsonify, url_for
from flask_cors import CORS  # Import CORS
import os
import logging
from config import BASE_DIR

# Stage 1: Initializing Flask App
# Since we are creating an app that accepts requests from the browser
# CORS has to be set up via flask-cors module
app = Flask(__name__)
CORS(app)


# Stage 2: Import the blueprints
from routes.route_inner_registry import inner_registry_bp
from routes.route_outer_registry import outer_registry_bp
from routes.route_priority_registry import priority_registry_bp

app.register_blueprint(inner_registry_bp)
app.register_blueprint(outer_registry_bp) 
app.register_blueprint(priority_registry_bp)

# Create a route for serving saved files

@app.route('/saves/<filename>', methods = ['GET'])
def download_file(filename):
    '''
    Downloads a file from the 'saves' directory.

    Args:
        filename (str): The name of the file to be downloaded.

    Returns:
        Response (file): The file to be downloaded as an attachment.

    '''
    # base_dir = os.path.dirname(os.path.abspath(__file__))
    directory = os.path.join(BASE_DIR, 'saves')
    return send_from_directory(directory, filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=False, port=25351, host = '192.168.30.19')
    # app.run(debug=False, port=25351, host = '127.0.0.1')
    logging.basicConfig(level=logging.INFO)
