from google.cloud import bigquery

CHARGING_STATIONS_SCHEMA = [
    bigquery.SchemaField("Station_ID", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("Latitude", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("Longitude", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("Address", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("Charger_Type", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("Cost", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("Availability", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("Distance_to_City", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("Usage_Stats", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("Station_Operator", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("Charging_Capacity", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("Connector_Types", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("Installation_Year", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("Renewable_Energy_Source", "BOOLEAN", mode="REQUIRED"),
    bigquery.SchemaField("Reviews", "FLOAT64", mode="REQUIRED"),
    bigquery.SchemaField("Parking_Spots", "INTEGER", mode="REQUIRED"),
    bigquery.SchemaField("Maintenance_Frequency", "STRING", mode="REQUIRED")
] 