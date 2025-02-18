from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User
from app.database import BigQueryDatabase
import logging
import uuid
import traceback
from app.auth import bp

logger = logging.getLogger(__name__)
db = BigQueryDatabase()

@bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        logger.info(f"Registration attempt for username: {data.get('username')}")
        
        # Check for required fields
        if not all(k in data for k in ['username', 'email', 'password']):
            return jsonify({'error': 'Missing required fields'}), 400

        # Check if username already exists
        if db.check_username_exists(data['username']):
            return jsonify({'error': 'Username already exists'}), 400

        # Generate UUID for new user
        user_id = str(uuid.uuid4())
        
        # Create user
        user_data = {
            'user_id': user_id,
            'username': data['username'],
            'email': data['email'],
            'password_hash': generate_password_hash(data['password'])
        }
        
        db.create_user(user_data)
        logger.info(f"Successfully registered user: {user_data['username']} with ID: {user_id}")
        
        return jsonify({'message': 'Registration successful'}), 201

    except Exception as e:
        logger.error(f"Registration error: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500

@bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        logger.info(f"Login attempt for username: {data.get('username')}")
        
        # Check for required fields
        if not all(k in data for k in ['username', 'password']):
            logger.error("Missing required fields")
            return jsonify({'error': 'Missing required fields'}), 400

        # Get user from database
        user_data = db.get_user_by_username(data['username'])
        if not user_data:
            logger.error(f"No user found with username: {data.get('username')}")
            return jsonify({'error': 'Login failed'}), 401

        logger.info(f"Found user: {user_data['username']}")

        # Check password
        if not check_password_hash(user_data['password_hash'], data['password']):
            logger.error("Password check failed")
            return jsonify({'error': 'Login failed'}), 401

        # Create user object and log them in
        user = User(user_data)
        login_user(user)
        logger.info(f"Successfully logged in user: {user.username}")

        return jsonify({'message': 'Login successful'}), 200

    except Exception as e:
        logger.error(f"Login error: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'error': 'Login failed'}), 500

@bp.route('/logout', methods=['POST'])
def logout():
    try:
        logout_user()
        return jsonify({'message': 'Logged out successfully'}), 200
    except Exception as e:
        logger.error(f"Logout error: {str(e)}")
        return jsonify({'error': 'Logout failed'}), 500 