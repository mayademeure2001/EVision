from google.cloud import bigquery

USERS_SCHEMA = [
    bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("username", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("email", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("password_hash", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("created_at", "TIMESTAMP", mode="REQUIRED")
]

TRIPS_SCHEMA = [
    bigquery.SchemaField("trip_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("user_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("car_type", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("battery_level_start", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("start_lat", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("start_lng", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("end_lat", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("end_lng", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("start_date", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("duration_seconds", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("distance_meters", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("average_speed_kph", "FLOAT", mode="REQUIRED"),
    bigquery.SchemaField("route_geometry", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("energy_used_kWh", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("cost_dollars", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("start_battery_capacity_kWh", "FLOAT", mode="NULLABLE")
]

TRIP_STATIONS_SCHEMA = [
    bigquery.SchemaField("trip_station_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("trip_id", "STRING", mode="REQUIRED"),
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

CAR_ENERGY_COSTS_SCHEMA = [
    bigquery.SchemaField("Vehicle", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("A", "INTEGER", mode="NULLABLE"),
    bigquery.SchemaField("B", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("C", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("BatteryCapacity_kWh", "FLOAT", mode="NULLABLE"),
    bigquery.SchemaField("CostPer_kWh_Dollars", "FLOAT", mode="NULLABLE")
] 