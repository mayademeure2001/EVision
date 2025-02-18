from flask import Blueprint

bp = Blueprint('trips', __name__)

from app.trips import routes 