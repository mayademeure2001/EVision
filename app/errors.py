from flask import jsonify

def handle_404_error(e):
    return jsonify({'error': 'Not found'}), 404

def handle_500_error(e):
    return jsonify({'error': 'Internal server error'}), 500 