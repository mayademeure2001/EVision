from flask import current_app
from google.cloud import bigquery
from google.oauth2 import service_account
import logging
import os
from config import Config
from werkzeug.security import check_password_hash
import requests
import json
from app.services.charging import ChargingService
import uuid
import traceback

logger = logging.getLogger(__name__)

class BigQueryDatabase:
    def __init__(self):
        # Initialize BigQuery client using application default credentials
        self.client = bigquery.Client(project=Config.GCP_PROJECT_ID)
        self.dataset = Config.BQ_DATASET
        self.users_table = 'users'
        self.trips_table = 'trips'
        self.trip_stations_table = 'trip_stations'
        self.osrm_base_url = Config.OSRM_BASE_URL

    @staticmethod
    def execute_query(query, params=None):
        try:
            job_config = bigquery.QueryJobConfig(
                query_parameters=params if params else []
            )
            query_job = current_app.bigquery_client.query(query, job_config=job_config)
            return query_job.result()
        except Exception as e:
            logger.error(f"Database error: {str(e)}")
            raise

    def get_user_by_username(self, username):
        query = f"""
        SELECT user_id, username, email, password_hash, created_at
        FROM `{self.dataset}.{self.users_table}`
        WHERE username = @username
        LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("username", "STRING", username)
            ]
        )
        
        results = self.client.query(query, job_config=job_config).result()
        user = next(iter(results), None)
        
        if user:
            user_dict = dict(user)
            logger.info(f"Found user data: {user_dict}")  # Debug log
            return user_dict
        return None

    def create_user(self, user_data):
        query = f"""
        INSERT INTO `{self.dataset}.{self.users_table}`
        (user_id, username, email, password_hash, created_at)
        VALUES
        (@user_id, @username, @email, @password_hash, CURRENT_TIMESTAMP())
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_data['user_id']),
                bigquery.ScalarQueryParameter("username", "STRING", user_data['username']),
                bigquery.ScalarQueryParameter("email", "STRING", user_data['email']),
                bigquery.ScalarQueryParameter("password_hash", "STRING", user_data['password_hash'])
            ]
        )
        
        self.client.query(query, job_config=job_config).result()

    def create_trip(self, user_id, car_type, battery_level_start, start_coords, end_coords):
        try:
            # Generate UUID for new trip
            trip_id = str(uuid.uuid4())
            logger.info(f"Creating trip with ID: {trip_id}")
            
            # Get route from OSRM
            route_url = f"{self.osrm_base_url}{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}?geometries=geojson&overview=full"
            logger.info(f"Calling OSRM with URL: {route_url}")
            
            response = requests.get(route_url)
            route_data = response.json()
            
            logger.info(f"OSRM Response: {route_data}")
            
            if response.status_code != 200 or 'routes' not in route_data or not route_data['routes']:
                raise Exception("Failed to get route from OSRM")
            
            route = route_data['routes'][0]
            
            # Find charging stations
            stations = self.find_charging_stations_along_route(route['geometry'])
            logger.info(f"Found {len(stations)} stations")
            
            # Store trip in BigQuery
            query = f"""
            INSERT INTO `{self.dataset}.{self.trips_table}`
            (trip_id, user_id, car_type, battery_level_start, start_lat, start_lng, 
             end_lat, end_lng, start_date, duration_seconds, distance_meters, 
             average_speed_kph, estimated_duration_battery_seconds, route_geometry)
            VALUES
            (@trip_id, @user_id, @car_type, @battery_level_start, @start_lat, @start_lng,
             @end_lat, @end_lng, CURRENT_TIMESTAMP(), @duration_seconds, @distance_meters,
             @average_speed_kph, @estimated_duration_battery, @route_geometry)
            """
            
            params = [
                bigquery.ScalarQueryParameter("trip_id", "STRING", trip_id),
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id),
                bigquery.ScalarQueryParameter("car_type", "STRING", car_type),
                bigquery.ScalarQueryParameter("battery_level_start", "FLOAT64", battery_level_start),
                bigquery.ScalarQueryParameter("start_lat", "FLOAT64", start_coords[0]),
                bigquery.ScalarQueryParameter("start_lng", "FLOAT64", start_coords[1]),
                bigquery.ScalarQueryParameter("end_lat", "FLOAT64", end_coords[0]),
                bigquery.ScalarQueryParameter("end_lng", "FLOAT64", end_coords[1]),
                bigquery.ScalarQueryParameter("duration_seconds", "INTEGER", int(route['duration'])),
                bigquery.ScalarQueryParameter("distance_meters", "FLOAT64", route['distance']),
                bigquery.ScalarQueryParameter("average_speed_kph", "FLOAT64", (route['distance']/1000)/(route['duration']/3600)),
                bigquery.ScalarQueryParameter("estimated_duration_battery", "INTEGER", int(route['duration'] * 1.2)),
                bigquery.ScalarQueryParameter("route_geometry", "STRING", json.dumps(route['geometry']))
            ]
            
            logger.info("Executing trip insert query")
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            self.client.query(query, job_config=job_config).result()
            
            # Store stations
            for station in stations:
                station_id = str(uuid.uuid4())
                station_query = f"""
                INSERT INTO `{self.dataset}.{self.trip_stations_table}`
                (trip_station_id, trip_id, station_id, name, latitude, longitude, 
                 address, distance_km, connection_types, power_kw, status)
                VALUES
                (@station_id, @trip_id, @ocm_id, @name, @lat, @lng, 
                 @address, @distance, @connections, @power, @status)
                """
                
                station_params = [
                    bigquery.ScalarQueryParameter("station_id", "STRING", station_id),
                    bigquery.ScalarQueryParameter("trip_id", "STRING", trip_id),
                    bigquery.ScalarQueryParameter("ocm_id", "INTEGER", station['id']),
                    bigquery.ScalarQueryParameter("name", "STRING", station['name']),
                    bigquery.ScalarQueryParameter("lat", "FLOAT64", station['latitude']),
                    bigquery.ScalarQueryParameter("lng", "FLOAT64", station['longitude']),
                    bigquery.ScalarQueryParameter("address", "STRING", station['address']),
                    bigquery.ScalarQueryParameter("distance", "FLOAT64", station['distance_km']),
                    bigquery.ScalarQueryParameter("connections", "STRING", json.dumps(station['connections'])),
                    bigquery.ScalarQueryParameter("power", "FLOAT64", station['max_power']),
                    bigquery.ScalarQueryParameter("status", "STRING", station['status'])
                ]
                
                logger.info(f"Storing station {station_id}")
                job_config = bigquery.QueryJobConfig(query_parameters=station_params)
                self.client.query(station_query, job_config=job_config).result()
            
            return {
                'trip_id': trip_id,
                'route': {
                    'distance': route['distance'],
                    'duration': route['duration'],
                    'geometry': route['geometry']
                },
                'stations': stations
            }

        except Exception as e:
            logger.error(f"Error creating trip: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    def get_user_trips(self, username):
        """Get all trips for a specific user"""
        query = f"""
        SELECT *
        FROM `{self.dataset}.{self.trips_table}`
        WHERE username = @username
        ORDER BY start_date DESC
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("username", "STRING", username)
            ]
        )
        
        results = self.client.query(query, job_config=job_config).result()
        return [dict(row) for row in results]

    @staticmethod
    def search_trips(user_id, start_date=None, end_date=None, destination=None, min_cost=None, max_cost=None):
        where_clauses = ["user_id = @user_id"]
        params = [bigquery.ScalarQueryParameter("user_id", "STRING", user_id)]

        if start_date:
            where_clauses.append("date >= @start_date")
            params.append(bigquery.ScalarQueryParameter("start_date", "TIMESTAMP", start_date))
        
        if end_date:
            where_clauses.append("date <= @end_date")
            params.append(bigquery.ScalarQueryParameter("end_date", "TIMESTAMP", end_date))
        
        if destination:
            where_clauses.append("destination LIKE @destination")
            params.append(bigquery.ScalarQueryParameter("destination", "STRING", f"%{destination}%"))
        
        if min_cost is not None:
            where_clauses.append("cost >= @min_cost")
            params.append(bigquery.ScalarQueryParameter("min_cost", "FLOAT64", min_cost))
        
        if max_cost is not None:
            where_clauses.append("cost <= @max_cost")
            params.append(bigquery.ScalarQueryParameter("max_cost", "FLOAT64", max_cost))

        query = f"""
        SELECT *
        FROM `{current_app.config['BQ_DATASET']}.{current_app.config['BQ_TRIPS_TABLE']}`
        WHERE {' AND '.join(where_clauses)}
        ORDER BY date DESC
        """

        return [dict(row) for row in BigQueryDatabase.execute_query(query, params)]

    @staticmethod
    def get_user_trip_stats(user_id):
        query = f"""
        SELECT 
            COUNT(*) as total_trips,
            SUM(cost) as total_cost,
            SUM(energy_consumed) as total_energy,
            AVG(cost) as avg_cost_per_trip,
            AVG(energy_consumed) as avg_energy_per_trip
        FROM `{current_app.config['BQ_DATASET']}.{current_app.config['BQ_TRIPS_TABLE']}`
        WHERE user_id = @user_id
        """
        
        params = [bigquery.ScalarQueryParameter("user_id", "STRING", user_id)]
        results = BigQueryDatabase.execute_query(query, params)
        return dict(next(results))

    def get_charging_stations(self, filters=None):
        query = f"""
        SELECT *
        FROM `capsone-maya-demeure.{self.dataset}.{self.table}`
        WHERE 1=1
        """

        if filters:
            if 'max_distance' in filters:
                query += f" AND Distance_to_City <= {filters['max_distance']}"
            if 'min_rating' in filters:
                query += f" AND Reviews >= {filters['min_rating']}"
            if 'charger_type' in filters:
                query += f" AND Charger_Type = '{filters['charger_type']}'"

        query_job = self.client.query(query)
        return query_job.result()

    def get_nearby_stations(self, latitude, longitude, radius_km=10):
        query = f"""
        SELECT 
            *,
            ST_DISTANCE(
                ST_GEOGPOINT(Longitude, Latitude),
                ST_GEOGPOINT(@user_long, @user_lat)
            ) / 1000 as distance_km
        FROM `capsone-maya-demeure.{self.dataset}.{self.table}`
        WHERE ST_DWITHIN(
            ST_GEOGPOINT(Longitude, Latitude),
            ST_GEOGPOINT(@user_long, @user_lat),
            @radius * 1000
        )
        ORDER BY distance_km
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_lat", "FLOAT64", latitude),
                bigquery.ScalarQueryParameter("user_long", "FLOAT64", longitude),
                bigquery.ScalarQueryParameter("radius", "FLOAT64", radius_km),
            ]
        )

        query_job = self.client.query(query, job_config=job_config)
        return query_job.result()

    def get_station_details(self, station_id):
        query = f"""
        SELECT *
        FROM `capsone-maya-demeure.{self.dataset}.{self.table}`
        WHERE Station_ID = @station_id
        """

        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("station_id", "STRING", station_id),
            ]
        )

        query_job = self.client.query(query, job_config=job_config)
        result = list(query_job.result())
        return result[0] if result else None

    def list_tables(self):
        """List all tables in the dataset for debugging"""
        try:
            tables = list(self.client.list_tables(f"{self.client.project}.{self.dataset}"))
            return [table.table_id for table in tables]
        except Exception as e:
            print(f"Error listing tables: {str(e)}")
            return []

    def test_connection(self):
        """Test the connection and table existence"""
        try:
            # Try to get table info
            table_ref = self.client.dataset(self.dataset).table(self.table)
            table = self.client.get_table(table_ref)
            print(f"Table {self.table} exists with {table.num_rows} rows")
            print(f"Schema: {[field.name for field in table.schema]}")
            return True
        except Exception as e:
            print(f"Error connecting to table: {str(e)}")
            return False

    def search_stations(self, params):
        """Search stations with filters"""
        try:
            conditions = []
            query_params = []

            if params.get('operator'):
                conditions.append("Station_Operator LIKE @operator")
                query_params.append(
                    bigquery.ScalarQueryParameter(
                        "operator", "STRING", f"%{params['operator']}%"
                    )
                )

            if params.get('max_cost') is not None:
                conditions.append("Cost_USD_kWh <= @max_cost")
                query_params.append(
                    bigquery.ScalarQueryParameter(
                        "max_cost", "FLOAT64", float(params['max_cost'])
                    )
                )

            # Build the WHERE clause
            where_clause = " AND ".join(conditions) if conditions else "1=1"

            query = f"""
            SELECT *
            FROM `{self.dataset}.{self.table}`
            WHERE {where_clause}
            LIMIT 10
            """

            job_config = bigquery.QueryJobConfig(query_parameters=query_params)
            results = self.client.query(query, job_config=job_config).result()
            
            return [dict(row) for row in results]

        except Exception as e:
            print(f"Search error: {str(e)}")
            raise

    def store_trip_stations(self, trip_id, stations):
        """Store charging stations found for a specific trip"""
        if not stations:
            return
        
        rows_to_insert = []
        for station in stations:
            for connection in station.get('connections', []):
                rows_to_insert.append({
                    'trip_id': trip_id,
                    'station_id': station.get('id'),
                    'name': station.get('name'),
                    'latitude': station.get('latitude'),
                    'longitude': station.get('longitude'),
                    'address': station.get('address'),
                    'distance_km': station.get('distance_km'),
                    'connection_types': connection.get('type'),
                    'power_kw': connection.get('power_kw'),
                    'status': connection.get('status')
                })

        if rows_to_insert:
            query = f"""
            INSERT INTO `{self.dataset}.{self.trip_stations_table}`
            (trip_id, station_id, name, latitude, longitude, address, 
             distance_km, connection_types, power_kw, status)
            VALUES
            """
            value_parts = []
            params = []
            param_num = 0

            for row in rows_to_insert:
                value_parts.append(f"""(
                    @p{param_num}, @p{param_num+1}, @p{param_num+2}, @p{param_num+3}, 
                    @p{param_num+4}, @p{param_num+5}, @p{param_num+6}, @p{param_num+7}, 
                    @p{param_num+8}, @p{param_num+9}
                )""")
                params.extend([
                    bigquery.ScalarQueryParameter(f"p{param_num}", "STRING", row['trip_id']),
                    bigquery.ScalarQueryParameter(f"p{param_num+1}", "STRING", row['station_id']),
                    bigquery.ScalarQueryParameter(f"p{param_num+2}", "STRING", row['name']),
                    bigquery.ScalarQueryParameter(f"p{param_num+3}", "FLOAT64", row['latitude']),
                    bigquery.ScalarQueryParameter(f"p{param_num+4}", "FLOAT64", row['longitude']),
                    bigquery.ScalarQueryParameter(f"p{param_num+5}", "STRING", row['address']),
                    bigquery.ScalarQueryParameter(f"p{param_num+6}", "FLOAT64", row['distance_km']),
                    bigquery.ScalarQueryParameter(f"p{param_num+7}", "STRING", row['connection_types']),
                    bigquery.ScalarQueryParameter(f"p{param_num+8}", "FLOAT64", row['power_kw']),
                    bigquery.ScalarQueryParameter(f"p{param_num+9}", "STRING", row['status'])
                ])
                param_num += 10

            query += ",".join(value_parts)
            
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            self.client.query(query, job_config=job_config).result()

    def check_username_exists(self, username):
        query = f"""
        SELECT COUNT(*) as count 
        FROM `{self.dataset}.{self.users_table}`
        WHERE username = @username
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("username", "STRING", username)
            ]
        )
        
        result = self.client.query(query, job_config=job_config).result()
        count = next(iter(result)).count
        return count > 0

    def check_email_exists(self, email):
        query = f"""
        SELECT COUNT(*) as count 
        FROM `{self.dataset}.{self.users_table}`
        WHERE email = @email
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("email", "STRING", email)
            ]
        )
        
        result = self.client.query(query, job_config=job_config).result()
        count = next(iter(result)).count
        return count > 0

    def get_user_by_id(self, user_id):
        query = f"""
        SELECT user_id, username, email, password_hash, created_at
        FROM `{self.dataset}.{self.users_table}`
        WHERE user_id = @user_id
        LIMIT 1
        """
        
        job_config = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("user_id", "STRING", user_id)
            ]
        )
        
        results = self.client.query(query, job_config=job_config).result()
        user = next(iter(results), None)
        
        if user:
            return dict(user)
        return None

    def find_charging_stations_along_route(self, route_geometry):
        try:
            coordinates = route_geometry['coordinates']
            sample_points = coordinates[::50]
            logger.info(f"Sampling {len(sample_points)} points from {len(coordinates)} coordinates")
            
            stations = []
            for coord in sample_points:
                lng, lat = coord
                
                ocm_url = f"https://api.openchargemap.io/v3/poi/?output=json&latitude={lat}&longitude={lng}&distance=10&distanceunit=km&maxresults=10"
                headers = {
                    "X-API-Key": Config.OCM_API_KEY,
                    "User-Agent": "EV_Route_Planner/1.0"
                }
                
                response = requests.get(ocm_url, headers=headers)
                if response.status_code != 200:
                    continue
                    
                for station in response.json():
                    try:
                        station_info = self._process_station(station)
                        if station_info:
                            stations.append(station_info)
                    except Exception as e:
                        logger.error(f"Error processing station: {str(e)}")
                        continue
            
            return list({station['id']: station for station in stations}.values())
            
        except Exception as e:
            logger.error(f"Error finding stations: {str(e)}")
            return []

    def _process_station(self, station):
        """Helper method to process a single station"""
        try:
            station_info = {
                'id': station['ID'],
                'name': station.get('AddressInfo', {}).get('Title', 'Unknown Station'),
                'latitude': station.get('AddressInfo', {}).get('Latitude'),
                'longitude': station.get('AddressInfo', {}).get('Longitude'),
                'address': station.get('AddressInfo', {}).get('AddressLine1', ''),
                'distance_km': station.get('AddressInfo', {}).get('Distance', 0),
                'connections': [
                    {
                        'type': conn.get('ConnectionType', {}).get('Title', 'Unknown'),
                        'power_kw': conn.get('PowerKW', 0),
                        'status': conn.get('StatusType', {}).get('Title', 'Unknown')
                    }
                    for conn in station.get('Connections', [])
                ],
                'max_power': max([conn.get('PowerKW', 0) for conn in station.get('Connections', [])], default=0),
                'status': 'Available'
            }
            
            if all(v is not None for v in [station_info['latitude'], station_info['longitude']]):
                return station_info
            return None
            
        except Exception as e:
            logger.error(f"Error processing station data: {str(e)}")
            return None

def load_charging_stations_data(csv_file_path):
    """
    Load charging stations data from CSV to BigQuery
    """
    try:
        # Configure the load job
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            schema=CHARGING_STATIONS_SCHEMA,
        )

        # Get the table reference
        dataset_ref = current_app.bigquery_client.dataset(current_app.config['BQ_DATASET'])
        table_ref = dataset_ref.table(current_app.config['BQ_STATIONS_TABLE'])

        # Load the CSV file
        with open(csv_file_path, "rb") as source_file:
            job = current_app.bigquery_client.load_table_from_file(
                source_file,
                table_ref,
                job_config=job_config
            )

        # Wait for the job to complete
        job.result()

        logger.info(f"Loaded {job.output_rows} rows into {current_app.config['BQ_DATASET']}.{current_app.config['BQ_STATIONS_TABLE']}")
        return True

    except Exception as e:
        logger.error(f"Error loading charging stations data: {str(e)}")
        raise

def search_stations(search_params):
    """
    Search charging stations based on various criteria
    """
    where_clauses = []
    params = []

    if search_params.get('operator'):
        where_clauses.append("Station_Operator = @operator")
        params.append(bigquery.ScalarQueryParameter("operator", "STRING", search_params['operator']))

    if search_params.get('charger_type'):
        where_clauses.append("Charger_Type = @charger_type")
        params.append(bigquery.ScalarQueryParameter("charger_type", "STRING", search_params['charger_type']))

    if search_params.get('max_cost'):
        where_clauses.append("Cost <= @max_cost")
        params.append(bigquery.ScalarQueryParameter("max_cost", "FLOAT64", search_params['max_cost']))

    query = f"""
    SELECT *
    FROM `{current_app.config['BQ_DATASET']}.{current_app.config['BQ_STATIONS_TABLE']}`
    {f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""}
    """

    return BigQueryDatabase.execute_query(query, params) 