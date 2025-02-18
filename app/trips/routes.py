from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.database import BigQueryDatabase
from app.services.charging import ChargingService
import logging
import traceback
import json

bp = Blueprint('trips', __name__)
logger = logging.getLogger(__name__)
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
        
        # Validate required fields
        required_fields = [
            'start_lat', 'start_lng', 'end_lat', 'end_lng',
            'car_type', 'battery_level_start'
        ]
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        # Validate car type
        if data['car_type'] not in VALID_CAR_TYPES:
            return jsonify({
                'error': 'Invalid car type',
                'valid_cars': VALID_CAR_TYPES
            }), 400

        # Validate battery level
        battery_level = float(data['battery_level_start'])
        if not 0 <= battery_level <= 100:
            return jsonify({
                'error': 'Battery level must be between 0 and 100'
            }), 400

        start_coords = (float(data['start_lat']), float(data['start_lng']))
        end_coords = (float(data['end_lat']), float(data['end_lng']))

        # Create the trip (this now includes getting route geometry)
        trip = db.create_trip(
            username=current_user.username,
            car_type=data['car_type'],
            battery_level_start=battery_level,
            start_coords=start_coords,
            end_coords=end_coords
        )

        return jsonify({
            'message': 'Trip created successfully',
            'trip': trip,
        }), 201

    except Exception as e:
        logger.error(f"Error creating trip: {str(e)}\n{traceback.format_exc()}")
        return jsonify({
            'error': 'Failed to create trip',
            'details': str(e)
        }), 500

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