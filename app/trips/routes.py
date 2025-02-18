from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.database import BigQueryDatabase
from app.services.charging import ChargingService
import logging
import traceback
import json
from app.trips import bp
import uuid

# Set up logger
logger = logging.getLogger(__name__)

# Create database instance
db = BigQueryDatabase()

VALID_CAR_TYPES = [
    'Tesla Model 3',
    'Nissan Leaf',
    'BMW i4',
    'Hyundai Ioniq 5',
    'Ford Mustang Mach-E',
    'Chevrolet Bolt EV',
    'Audi e-tron',
    'Kia EV6',
    'Porsche Taycan',
    'Volkswagen ID.4'
]

@bp.route('/create', methods=['POST'])
@login_required
def create_trip():
    try:
        data = request.get_json()
        
        # Validate input
        required_fields = ['start_lat', 'start_lng', 'end_lat', 'end_lng', 
                         'car_type', 'battery_level_start']
        if not all(k in data for k in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Create trip
        result = db.create_trip(
            user_id=current_user.id,
            car_type=data['car_type'],
            battery_level_start=data['battery_level_start'],
            start_coords=(data['start_lat'], data['start_lng']),
            end_coords=(data['end_lat'], data['end_lng'])
        )
        
        return jsonify(result), 201
        
    except Exception as e:
        logger.error(f"Error creating trip: {str(e)}")
        return jsonify({'error': 'Failed to create trip'}), 500

@bp.route('/list', methods=['GET'])
@login_required
def list_trips():
    try:
        trips = db.get_user_trips(current_user.username)
        # Format the response to include route geometry
        formatted_trips = [{
            **trip,
            'route_geometry': json.loads(trip['route_geometry']) if trip.get('route_geometry') else None
        } for trip in trips]
        return jsonify({'trips': formatted_trips}), 200
    except Exception as e:
        logger.error(f"Error listing trips: {str(e)}")
        return jsonify({'error': 'Failed to retrieve trips'}), 500 