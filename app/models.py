from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['username']  # Use username as ID
        self.username = user_data['username']
        self.email = user_data['email']
        self.password_hash = user_data['password_hash']
        self.created_at = user_data.get('created_at')

    def set_password(self, password):
        return generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Trip:
    def __init__(self, trip_data):
        self.id = trip_data.get('id')
        self.user_id = trip_data.get('user_id')
        self.start_point = trip_data.get('start_point')
        self.destination = trip_data.get('destination')
        self.ev_model = trip_data.get('ev_model')
        self.battery_level = trip_data.get('battery_level')
        self.date = trip_data.get('date')
        self.cost = trip_data.get('cost')
        self.energy_consumed = trip_data.get('energy_consumed')
        self.charging_stops = trip_data.get('charging_stops', []) 