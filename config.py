import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-please-change'
    SESSION_TYPE = 'filesystem'
    REMEMBER_COOKIE_SECURE = False  # Set to True in production
    SESSION_COOKIE_SECURE = False   # Set to True in production
    
    # API Keys
    OCM_API_KEY = "29d4d261-f1f8-4c50-b969-258a2cb37ea4"
    
    # Database Config
    GCP_PROJECT_ID = "capsone-maya-demeure"
    BQ_DATASET = "ev_tracker"
    
    # OSRM Config
    OSRM_BASE_URL = "http://router.project-osrm.org/route/v1/driving/" 
    
    # Add table names
    BQ_USERS_TABLE = 'users'
    BQ_TRIPS_TABLE = 'trips'
    BQ_TRIP_STATIONS_TABLE = 'trip_stations'
    BQ_CAR_BATTERY_TABLE = 'car_battery_speed' 