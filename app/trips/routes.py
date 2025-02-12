from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from app.database import BigQueryDatabase
from datetime import datetime
import logging

bp = Blueprint('trips', __name__)
logger = logging.getLogger(__name__)

@bp.route('/add', methods=['POST'])
@login_required
def add_trip():
    try:
        data = request.get_json()
        # Validate required fields
        required_fields = ['start_point', 'destination', 'ev_model', 'battery_level']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        # Calculate trip details including charging stops
        trip_details = calculate_trip_details(
            data['start_point'],
            data['destination'],
            data['ev_model'],
            data['battery_level']
        )

        # Add trip to database
        trip_id = BigQueryDatabase.create_trip(
            user_id=current_user.id,
            start_point=data['start_point'],
            destination=data['destination'],
            ev_model=data['ev_model'],
            battery_level=data['battery_level'],
            cost=trip_details['total_cost'],
            energy_consumed=trip_details['energy_consumed'],
            charging_stops=trip_details['charging_stops']
        )

        return jsonify({
            'message': 'Trip added successfully',
            'trip_id': trip_id,
            'details': trip_details
        }), 201

    except Exception as e:
        logger.error(f"Error adding trip: {str(e)}")
        return jsonify({'error': 'Failed to add trip'}), 500

@bp.route('/search', methods=['GET'])
@login_required
def search_trips():
    try:
        # Get search parameters from query string
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        destination = request.args.get('destination')
        min_cost = request.args.get('min_cost', type=float)
        max_cost = request.args.get('max_cost', type=float)
        
        trips = BigQueryDatabase.search_trips(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            destination=destination,
            min_cost=min_cost,
            max_cost=max_cost
        )
        
        return jsonify({'trips': trips}), 200

    except Exception as e:
        logger.error(f"Error searching trips: {str(e)}")
        return jsonify({'error': 'Search failed'}), 500

@bp.route('/<int:trip_id>', methods=['GET'])
@login_required
def get_trip(trip_id):
    try:
        trip = BigQueryDatabase.get_trip(trip_id, current_user.id)
        if not trip:
            return jsonify({'error': 'Trip not found'}), 404
            
        return jsonify(trip), 200

    except Exception as e:
        logger.error(f"Error retrieving trip: {str(e)}")
        return jsonify({'error': 'Failed to retrieve trip'}), 500

@bp.route('/stats', methods=['GET'])
@login_required
def get_trip_stats():
    try:
        stats = BigQueryDatabase.get_user_trip_stats(current_user.id)
        return jsonify(stats), 200

    except Exception as e:
        logger.error(f"Error retrieving trip stats: {str(e)}")
        return jsonify({'error': 'Failed to retrieve trip statistics'}), 500

def calculate_trip_details(start_point, destination, ev_model, battery_level):
    """Calculate trip details including optimal charging stops"""
    # This is a placeholder for the actual implementation
    # You would need to implement the routing and charging logic here
    return {
        'total_cost': 0.0,
        'energy_consumed': 0.0,
        'charging_stops': [],
        'route': [],
        'total_distance': 0.0,
        'estimated_duration': 0.0
    } 