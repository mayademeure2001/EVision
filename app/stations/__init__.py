"""Stations blueprint package."""
from flask import Blueprint

bp = Blueprint('stations', __name__)

from app.stations import routes 