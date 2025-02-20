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
            trip_id = str(uuid.uuid4())
            
            # Get route from OSRM
            route_url = f"{self.osrm_base_url}{start_coords[1]},{start_coords[0]};{end_coords[1]},{end_coords[0]}?geometries=geojson&overview=full"
            response = requests.get(route_url)
            route_data = response.json()
            
            if response.status_code != 200 or 'routes' not in route_data or not route_data['routes']:
                raise Exception("Failed to get route from OSRM")
                
            route = route_data['routes'][0]
            
            # Calculate average speed
            average_speed_kph = (route['distance']/1000)/(route['duration']/3600)
            
            # Get vehicle efficiency parameters and battery capacity from car_energy_costs table
            query = f"""
            SELECT A, B, C, CostPer_kWh_Dollars, BatteryCapacity_kWh
            FROM `{self.dataset}.car_energy_costs`
            WHERE Vehicle = @car_type
            LIMIT 1
            """
            
            job_config = bigquery.QueryJobConfig(
                query_parameters=[
                    bigquery.ScalarQueryParameter("car_type", "STRING", car_type)
                ]
            )
            
            results = self.client.query(query, job_config=job_config).result()
            vehicle_data = next(iter(results), None)
            
            if not vehicle_data:
                raise Exception(f"No efficiency data found for vehicle type: {car_type}")
                
            # Calculate efficiency (Wh/km)
            efficiency = (vehicle_data['A'] + 
                         vehicle_data['B'] * average_speed_kph + 
                         vehicle_data['C'] * (average_speed_kph ** 2))
            
            # Calculate energy used (kWh)
            energy_used = (route['distance'] / 1000) * (efficiency / 1000)
            
            # Calculate cost
            cost = energy_used * vehicle_data['CostPer_kWh_Dollars']
            
            # Calculate start battery capacity in kWh
            start_battery_capacity = (battery_level_start / 100) * vehicle_data['BatteryCapacity_kWh']
            
            # Store trip in BigQuery
            query = f"""
            INSERT INTO `{self.dataset}.{Config.BQ_TRIPS_TABLE}`
            (trip_id, user_id, car_type, battery_level_start, 
             start_lat, start_lng, end_lat, end_lng,
             start_date, duration_seconds, distance_meters, 
             average_speed_kph, route_geometry, energy_used_kWh,
             cost_dollars, start_battery_capacity_kWh)
            VALUES
            (@trip_id, @user_id, @car_type, @battery_level_start,
             @start_lat, @start_lng, @end_lat, @end_lng,
             CURRENT_TIMESTAMP(), @duration_seconds, @distance_meters,
             @average_speed_kph, @route_geometry, @energy_used_kWh,
             @cost_dollars, @start_battery_capacity_kWh)
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
                bigquery.ScalarQueryParameter("average_speed_kph", "FLOAT64", average_speed_kph),
                bigquery.ScalarQueryParameter("route_geometry", "STRING", json.dumps(route['geometry'])),
                bigquery.ScalarQueryParameter("energy_used_kWh", "FLOAT64", energy_used),
                bigquery.ScalarQueryParameter("cost_dollars", "FLOAT64", cost),
                bigquery.ScalarQueryParameter("start_battery_capacity_kWh", "FLOAT64", start_battery_capacity)
            ]
            
            job_config = bigquery.QueryJobConfig(query_parameters=params)
            self.client.query(query, job_config=job_config).result()
            
            # Find and store charging stations
            stations = self.find_charging_stations_along_route(route['geometry'])
            self.store_trip_stations(trip_id, stations)
            
            return {
                'trip_id': trip_id,
                'route': {
                    'distance': route['distance'],
                    'duration': route['duration'],
                    'geometry': route['geometry']
                },
                'energy': {
                    'used_kWh': energy_used,
                    'cost_dollars': cost,
                    'start_battery_capacity_kWh': start_battery_capacity
                },
                'stations': stations
            }
            
        except Exception as e:
            logger.error(f"Error creating trip: {str(e)}")
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
            logger.info("No stations to store")
            return
        
        rows_to_insert = []
        for idx, station in enumerate(stations):
            if not station:  # Skip if station is None
                continue
            
            for connection in station.get('connections', []):
                trip_station_id = f"{trip_id}_{station['id']}_{idx}"
                try:
                    rows_to_insert.append({
                        'trip_station_id': trip_station_id,
                        'trip_id': trip_id,
                        'station_id': int(station['id']),
                        'name': station['name'][:100],  # Limit string length
                        'latitude': float(station['latitude']),
                        'longitude': float(station['longitude']),
                        'address': station['address'][:200] if station['address'] else 'No Address',  # Limit string length and provide default
                        'distance_km': float(station['distance_km']),
                        'connection_types': connection['type'][:50],  # Limit string length
                        'power_kw': float(connection['power_kw']),
                        'status': connection['status'][:50]  # Limit string length
                    })
                except (ValueError, KeyError) as e:
                    logger.error(f"Error processing station {trip_station_id}: {str(e)}")
                    continue

        if rows_to_insert:
            query = f"""
            INSERT INTO `{self.dataset}.{self.trip_stations_table}`
            (trip_station_id, trip_id, station_id, name, latitude, longitude, 
             address, distance_km, connection_types, power_kw, status)
            VALUES
            """
            value_parts = []
            params = []
            param_num = 0

            for row in rows_to_insert:
                value_parts.append(f"""(
                    @p{param_num}, @p{param_num+1}, @p{param_num+2}, @p{param_num+3}, 
                    @p{param_num+4}, @p{param_num+5}, @p{param_num+6}, @p{param_num+7}, 
                    @p{param_num+8}, @p{param_num+9}, @p{param_num+10}
                )""")
                params.extend([
                    bigquery.ScalarQueryParameter(f"p{param_num}", "STRING", row['trip_station_id']),
                    bigquery.ScalarQueryParameter(f"p{param_num+1}", "STRING", row['trip_id']),
                    bigquery.ScalarQueryParameter(f"p{param_num+2}", "INTEGER", row['station_id']),
                    bigquery.ScalarQueryParameter(f"p{param_num+3}", "STRING", row['name']),
                    bigquery.ScalarQueryParameter(f"p{param_num+4}", "FLOAT64", row['latitude']),
                    bigquery.ScalarQueryParameter(f"p{param_num+5}", "FLOAT64", row['longitude']),
                    bigquery.ScalarQueryParameter(f"p{param_num+6}", "STRING", row['address']),
                    bigquery.ScalarQueryParameter(f"p{param_num+7}", "FLOAT64", row['distance_km']),
                    bigquery.ScalarQueryParameter(f"p{param_num+8}", "STRING", row['connection_types']),
                    bigquery.ScalarQueryParameter(f"p{param_num+9}", "FLOAT64", row['power_kw']),
                    bigquery.ScalarQueryParameter(f"p{param_num+10}", "STRING", row['status'])
                ])
                param_num += 11

            query += ",".join(value_parts)
            
            try:
                job_config = bigquery.QueryJobConfig(query_parameters=params)
                self.client.query(query, job_config=job_config).result()
                logger.info(f"Successfully stored {len(rows_to_insert)} stations")
            except Exception as e:
                logger.error(f"Error storing stations: {str(e)}")
                raise

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
            # Add default values for required fields
            station_info = {
                'id': station.get('ID', 0),  # Default to 0 if no ID
                'name': station.get('AddressInfo', {}).get('Title', 'Unknown Station'),
                'latitude': station.get('AddressInfo', {}).get('Latitude', 0.0),
                'longitude': station.get('AddressInfo', {}).get('Longitude', 0.0),
                'address': station.get('AddressInfo', {}).get('AddressLine1', 'No Address'),  # Default address
                'distance_km': station.get('AddressInfo', {}).get('Distance', 0.0),
                'connections': []
            }
            
            # Process connections if they exist
            if station.get('Connections'):
                for conn in station['Connections']:
                    connection = {
                        'type': conn.get('ConnectionType', {}).get('Title', 'Unknown'),
                        'power_kw': float(conn.get('PowerKW', 0.0)),  # Convert to float with default
                        'status': conn.get('StatusType', {}).get('Title', 'Unknown')
                    }
                    station_info['connections'].append(connection)
            else:
                # Add a default connection if none exists
                station_info['connections'].append({
                    'type': 'Unknown',
                    'power_kw': 0.0,
                    'status': 'Unknown'
                })
            
            if all(v is not None for v in [station_info['latitude'], station_info['longitude']]):
                return station_info
            return None
            
        except Exception as e:
            logger.error(f"Error processing station data: {str(e)}")
            return None

    def search_trips(self, filters=None):
        """
        Search trips with various filters
        filters can include:
        - car_types: list of car types
        - user_id: string
        - min_duration, max_duration: in seconds
        - min_distance, max_distance: in meters
        - min_speed, max_speed: in kph
        - min_energy, max_energy: in kWh
        - min_cost, max_cost: in dollars
        """
        try:
            conditions = []
            params = []
            param_count = 0

            if filters:
                if filters.get('car_types'):
                    car_types = filters['car_types']
                    placeholders = [f'@car_type_{i}' for i in range(len(car_types))]
                    conditions.append(f"car_type IN ({','.join(placeholders)})")
                    for i, car_type in enumerate(car_types):
                        params.append(bigquery.ScalarQueryParameter(f"car_type_{i}", "STRING", car_type))

                if filters.get('user_id'):
                    conditions.append("user_id = @user_id")
                    params.append(bigquery.ScalarQueryParameter("user_id", "STRING", filters['user_id']))

                if filters.get('min_duration'):
                    conditions.append("duration_seconds >= @min_duration")
                    params.append(bigquery.ScalarQueryParameter("min_duration", "INTEGER", filters['min_duration']))
                if filters.get('max_duration'):
                    conditions.append("duration_seconds <= @max_duration")
                    params.append(bigquery.ScalarQueryParameter("max_duration", "INTEGER", filters['max_duration']))

                if filters.get('min_distance'):
                    conditions.append("distance_meters >= @min_distance")
                    params.append(bigquery.ScalarQueryParameter("min_distance", "FLOAT64", filters['min_distance']))
                if filters.get('max_distance'):
                    conditions.append("distance_meters <= @max_distance")
                    params.append(bigquery.ScalarQueryParameter("max_distance", "FLOAT64", filters['max_distance']))

                if filters.get('min_speed'):
                    conditions.append("average_speed_kph >= @min_speed")
                    params.append(bigquery.ScalarQueryParameter("min_speed", "FLOAT64", filters['min_speed']))
                if filters.get('max_speed'):
                    conditions.append("average_speed_kph <= @max_speed")
                    params.append(bigquery.ScalarQueryParameter("max_speed", "FLOAT64", filters['max_speed']))

                if filters.get('min_energy'):
                    conditions.append("energy_used_kWh >= @min_energy")
                    params.append(bigquery.ScalarQueryParameter("min_energy", "FLOAT64", filters['min_energy']))
                if filters.get('max_energy'):
                    conditions.append("energy_used_kWh <= @max_energy")
                    params.append(bigquery.ScalarQueryParameter("max_energy", "FLOAT64", filters['max_energy']))

                if filters.get('min_cost'):
                    conditions.append("cost_dollars >= @min_cost")
                    params.append(bigquery.ScalarQueryParameter("min_cost", "FLOAT64", filters['min_cost']))
                if filters.get('max_cost'):
                    conditions.append("cost_dollars <= @max_cost")
                    params.append(bigquery.ScalarQueryParameter("max_cost", "FLOAT64", filters['max_cost']))

            # Build the query
            query = f"""
            SELECT *
            FROM `{self.dataset}.{Config.BQ_TRIPS_TABLE}`
            {f"WHERE {' AND '.join(conditions)}" if conditions else ""}
            ORDER BY start_date DESC
            """

            job_config = bigquery.QueryJobConfig(query_parameters=params)
            results = self.client.query(query, job_config=job_config).result()
            
            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error searching trips: {str(e)}")
            raise

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