from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash
from flask_login import login_user, logout_user, login_required
from app.models import User
from app.database import BigQueryDatabase
import logging

bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)
db = BigQueryDatabase()

@bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not all([username, email, password]):
            return jsonify({'error': 'Missing required fields'}), 400

        existing_user = db.get_user_by_username(username)
        if existing_user:
            return jsonify({'error': 'Username already exists'}), 400

        password_hash = generate_password_hash(password)
        db.create_user(username, email, password_hash)
        
        return jsonify({'message': 'User registered successfully'}), 201

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        username = data.get('username')
        password = data.get('password')

        if not all([username, password]):
            return jsonify({'error': 'Missing username or password'}), 400

        user_data = db.get_user_by_username(username)
        if not user_data:
            return jsonify({'error': 'Invalid username or password'}), 401

        user = User(user_data)
        if not user.check_password(password):
            return jsonify({'error': 'Invalid username or password'}), 401

        login_user(user)
        return jsonify({'message': 'Login successful'}), 200

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    return jsonify({'message': 'Logged out successfully'}), 200 