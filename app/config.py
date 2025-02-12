import os

class Config:
    # Google Cloud settings (needed for BigQuery)
    GCP_PROJECT_ID = 'capsone-maya-demeure'
    
    # BigQuery dataset and table names
    BQ_DATASET = 'ev_tracker'
    BQ_STATIONS_TABLE = 'ev_charging_stations_converted'