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
    bigquery.SchemaField("start_lat", "FLOAT"),
    bigquery.SchemaField("start_lng", "FLOAT"),
    bigquery.SchemaField("end_lat", "FLOAT"),
    bigquery.SchemaField("end_lng", "FLOAT"),
    bigquery.SchemaField("start_date", "TIMESTAMP"),
    bigquery.SchemaField("duration_seconds", "INTEGER"),
    bigquery.SchemaField("distance_meters", "FLOAT")
] 