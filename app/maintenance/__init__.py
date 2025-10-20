from flask import Blueprint

bp = Blueprint('maintenance', __name__)

from app.maintenance import routes