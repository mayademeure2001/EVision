from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.database import BigQueryDatabase
from app.services.charging import ChargingService
import logging
import traceback

bp = Blueprint('trips', __name__)
logger = logging.getLogger(__name__)
db = BigQueryDatabase()

@bp.route('/create', methods=['POST'])
@login_required
def create_trip():
    try:
        data = request.get_json()
        
        required_fields = ['start_lat', 'start_lng', 'end_lat', 'end_lng']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required coordinates'}), 400

        start_coords = (float(data['start_lat']), float(data['start_lng']))
        end_coords = (float(data['end_lat']), float(data['end_lng']))

        # Create the trip
        trip = db.create_trip(
            username=current_user.username,
            start_coords=start_coords,
            end_coords=end_coords
        )

        # Find charging stations
        charging_service = ChargingService()
        stations = charging_service.find_stations_along_route(
            start_coords=start_coords,
            end_coords=end_coords,
            radius_km=data.get('charging_radius_km', 5)
        )

        # Store the stations
        if stations:
            db.store_trip_stations(trip['trip_id'], stations)

        return jsonify({
            'message': 'Trip created successfully',
            'trip': trip,
            'charging_stations': stations
        }), 201

    except Exception as e:
        logger.error(f"Error creating trip: {str(e)}")
        return jsonify({
            'error': 'Failed to create trip',
            'details': str(e)
        }), 500

@bp.route('/list', methods=['GET'])
@login_required
def list_trips():
    try:
        trips = db.get_user_trips(current_user.username)
        return jsonify({'trips': trips}), 200
    except Exception as e:
        logger.error(f"Error listing trips: {str(e)}")
        return jsonify({'error': 'Failed to retrieve trips'}), 500 