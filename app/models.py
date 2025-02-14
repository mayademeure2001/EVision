from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin):
    def __init__(self, user_data):
        self.id = user_data['username']
        self.username = user_data['username']
        self.email = user_data['email']
        self.password_hash = user_data['password_hash']
        self.created_at = user_data.get('created_at')

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Trip:
    def __init__(self, trip_data):
        self.trip_id = trip_data.get('trip_id')
        self.username = trip_data.get('username')
        self.start_lat = trip_data.get('start_lat')
        self.start_lng = trip_data.get('start_lng')
        self.end_lat = trip_data.get('end_lat')
        self.end_lng = trip_data.get('end_lng')
        self.start_date = trip_data.get('start_date')
        self.duration_seconds = trip_data.get('duration_seconds')
        self.distance_meters = trip_data.get('distance_meters') 