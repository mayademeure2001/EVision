print("Loading auth routes file...")  # Add this at the very top of the file

from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required
from app.database import BigQueryDatabase
import logging

# Create blueprint directly in routes.py
bp = Blueprint('auth', __name__)
logger = logging.getLogger(__name__)
db = BigQueryDatabase()

print("Loading auth routes...")  # Add this debug print

@bp.route('/', methods=['GET'])
def index():
    print("Index route accessed")
    return jsonify({'message': 'Auth index working!'}), 200

@bp.route('/test', methods=['GET'])
def test():
    return jsonify({'message': 'Auth test working!'}), 200

@bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        username = data.get('username')
        email = data.get('email')
        password = data.get('password')

        if not all([username, email, password]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Check if user exists
        existing_user = db.get_user_by_username(username)
        if existing_user:
            return jsonify({'error': 'Username already exists'}), 400

        # Create new user
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

        # Get user from database
        user_data = db.get_user_by_username(username)
        if not user_data:
            return jsonify({'error': 'User not found'}), 401

        # Create User object
        from app.models import User
        user = User(user_data)

        # Check password
        if not check_password_hash(user.password_hash, password):
            return jsonify({'error': 'Invalid password'}), 401

        # Log in user
        login_user(user)
        return jsonify({'message': 'Login successful'}), 200

    except Exception as e:
        logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    # Clear the session cookie
    response = jsonify({'message': 'Logout successful'})
    response.set_cookie('session', '', expires=0)  # Expire the cookie immediately
    return response, 200

@bp.route('/reset-password', methods=['POST'])
def reset_password():
    # TODO: Implement password reset functionality
    pass 