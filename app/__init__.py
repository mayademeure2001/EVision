from flask import Flask, jsonify
from flask_login import LoginManager
from google.cloud import bigquery
from app.models import User
from app.config import Config
from app.database import BigQueryDatabase

login_manager = LoginManager()

@login_manager.user_loader
def load_user(username):
    user_data = BigQueryDatabase().get_user_by_username(username)
    if user_data:
        return User(user_data)
    return None

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.secret_key = 'dev'  # Change this to a real secret key in production

    # Initialize BigQuery client
    app.bigquery_client = bigquery.Client(project=app.config['GCP_PROJECT_ID'])

    # Initialize Flask-Login
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    # Register blueprints
    from app.auth.routes import bp as auth_bp
    from app.stations import bp as stations_bp
    from app.trips import bp as trips_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(trips_bp, url_prefix='/trips')
    app.register_blueprint(stations_bp, url_prefix='/stations')

    return app 