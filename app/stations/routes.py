from flask import request, jsonify
from flask_login import login_required
from app.database import BigQueryDatabase
from google.cloud import bigquery
from app.stations import bp  # Import bp from __init__.py instead of creating new one
import logging

logger = logging.getLogger(__name__)
db = BigQueryDatabase()

@bp.route('/test', methods=['GET'])
def test():
    return jsonify({'message': 'Stations blueprint is working!'}), 200

@bp.route('/nearby', methods=['GET'])
@login_required
def get_nearby_stations():
    try:
        lat = float(request.args.get('lat'))
        lng = float(request.args.get('lng'))
        radius = float(request.args.get('radius', 5.0))

        print(f"Searching for stations near: {lat}, {lng} with radius {radius}km")

        # Create job config correctly
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("lat", "FLOAT64", lat),
                bigquery.ScalarQueryParameter("lng", "FLOAT64", lng),
                bigquery.ScalarQueryParameter("radius", "FLOAT64", radius)
            ]
        )

        query = f"""
        SELECT 
            *,
            ST_DISTANCE(
                ST_GEOGPOINT(Longitude, Latitude),
                ST_GEOGPOINT(@lng, @lat)
            ) as distance_meters
        FROM `{db.dataset}.{db.table}`
        WHERE 
            Latitude IS NOT NULL 
            AND Longitude IS NOT NULL
            AND ST_DWITHIN(
                ST_GEOGPOINT(Longitude, Latitude),
                ST_GEOGPOINT(@lng, @lat),
                @radius * 1000
            )
        ORDER BY distance_meters
        LIMIT 10
        """

        print(f"Running query with params: lat={lat}, lng={lng}, radius={radius}")
        results = db.client.query(query, job_config=job_config).result()
        stations = [dict(row) for row in results]
        print(f"Found {len(stations)} stations")

        # Convert distance to kilometers
        for station in stations:
            station['distance_km'] = station['distance_meters'] / 1000

        return jsonify({
            'stations': stations,
            'count': len(stations),
            'search_params': {
                'latitude': lat,
                'longitude': lng,
                'radius_km': radius
            }
        }), 200

    except ValueError as e:
        print(f"ValueError: {str(e)}")
        return jsonify({'error': 'Invalid coordinates'}), 400
    except Exception as e:
        print(f"Error finding nearby stations: {str(e)}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': 'Failed to find nearby stations'}), 500

@bp.route('/search', methods=['GET'])
@login_required
def search_stations():
    try:
        search_params = {
            'operator': request.args.get('operator'),
            'charger_type': request.args.get('charger_type'),
            'max_cost': request.args.get('max_cost', type=float),
            'min_rating': request.args.get('min_rating', type=float),
            'available_only': request.args.get('available_only', type=bool)
        }

        stations = BigQueryDatabase.search_stations(search_params)
        return jsonify({'stations': stations}), 200

    except Exception as e:
        logger.error(f"Error searching stations: {str(e)}")
        return jsonify({'error': 'Failed to search stations'}), 500

@bp.route('/route', methods=['POST'])
@login_required
def find_charging_route():
    try:
        data = request.get_json()
        required_fields = ['start_point', 'destination', 'ev_model', 'battery_level']
        if not all(field in data for field in required_fields):
            return jsonify({'error': 'Missing required fields'}), 400

        route = calculate_charging_route(
            start_point=data['start_point'],
            destination=data['destination'],
            ev_model=data['ev_model'],
            battery_level=data['battery_level']
        )

        return jsonify(route), 200

    except Exception as e:
        logger.error(f"Error calculating route: {str(e)}")
        return jsonify({'error': 'Failed to calculate route'}), 500

def calculate_charging_route(start_point, destination, ev_model, battery_level):
    """Calculate optimal route with charging stops"""
    # This is a placeholder for the actual implementation
    # You would need to implement the routing algorithm here
    return {
        'route': [],
        'charging_stops': [],
        'total_distance': 0.0,
        'total_duration': 0.0,
        'total_cost': 0.0,
        'energy_consumption': 0.0
    }

@bp.route('/debug', methods=['GET'])
def debug():
    try:
        # List all tables
        tables = db.list_tables()
        print(f"Found tables: {tables}")

        # Test connection to stations table
        connection_ok = db.test_connection()
        
        return jsonify({
            'tables': tables,
            'connection_ok': connection_ok
        }), 200
    except Exception as e:
        print(f"Debug error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/schema', methods=['GET'])
def get_schema():
    try:
        # Get table info
        table_ref = db.client.dataset(db.dataset).table(db.table)
        table = db.client.get_table(table_ref)
        
        # Get sample data
        query = f"""
        SELECT *
        FROM `{db.dataset}.{db.table}`
        LIMIT 1
        """
        sample = next(db.client.query(query).result())
        
        return jsonify({
            'schema': [{'name': field.name, 'type': field.field_type} for field in table.schema],
            'sample_row': dict(sample)
        }), 200
    except Exception as e:
        print(f"Schema error: {str(e)}")
        return jsonify({'error': str(e)}), 500 