from google.cloud import bigquery

USERS_SCHEMA = [
    bigquery.SchemaField("username", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("email", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("password_hash", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED")
]

TRIPS_SCHEMA = [
    bigquery.SchemaField("trip_id", "INTEGER"),
    bigquery.SchemaField("username", "STRING"),
    bigquery.SchemaField("car_type", "STRING"),
    bigquery.SchemaField("battery_level_start", "FLOAT"),
    bigquery.SchemaField("start_lat", "FLOAT"),
    bigquery.SchemaField("start_lng", "FLOAT"),
    bigquery.SchemaField("end_lat", "FLOAT"),
    bigquery.SchemaField("end_lng", "FLOAT"),
    bigquery.SchemaField("start_date", "TIMESTAMP"),
    bigquery.SchemaField("duration_seconds", "INTEGER"),
    bigquery.SchemaField("distance_meters", "FLOAT"),
    bigquery.SchemaField("average_speed_kph", "FLOAT"),
    bigquery.SchemaField("estimated_duration_battery_seconds", "INTEGER"),
    bigquery.SchemaField("route_geometry", "STRING")
]

TRIP_STATIONS_SCHEMA = [
    bigquery.SchemaField("trip_id", "INTEGER"),
    bigquery.SchemaField("station_id", "INTEGER"),
    bigquery.SchemaField("name", "STRING"),
    bigquery.SchemaField("latitude", "FLOAT"),
    bigquery.SchemaField("longitude", "FLOAT"),
    bigquery.SchemaField("address", "STRING"),
    bigquery.SchemaField("distance_km", "FLOAT"),
    bigquery.SchemaField("connection_types", "STRING"),
    bigquery.SchemaField("power_kw", "FLOAT"),
    bigquery.SchemaField("status", "STRING")
] 