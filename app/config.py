import os

class Config:
    # Google Cloud settings
    GCP_PROJECT_ID = 'capsone-maya-demeure'
    
    # BigQuery dataset and table names
    BQ_DATASET = 'ev_tracker'
    BQ_USERS_TABLE = 'users'
    BQ_TRIPS_TABLE = 'trips'
    BQ_TRIP_STATIONS_TABLE = 'trip_stations'
    
    # Open Charge Map config
    OCM_API_KEY = '78796da0-ae35-4cfc-8c3e-550d70f0e7e5'
    OCM_BASE_URL = 'https://api.openchargemap.io/v3'