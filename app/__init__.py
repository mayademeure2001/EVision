from flask import Flask
from flask_login import LoginManager
from flask_session import Session
from config import Config

login_manager = LoginManager()
sess = Session()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    sess.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    
    # Register blueprints
    from app.auth import bp as auth_bp
    from app.trips import bp as trips_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(trips_bp, url_prefix='/trips')
    
    return app

@login_manager.user_loader
def load_user(user_id):
    from app.models import User
    from app.database import BigQueryDatabase
    db = BigQueryDatabase()
    user_data = db.get_user_by_id(user_id)
    return User(user_data) if user_data else None 