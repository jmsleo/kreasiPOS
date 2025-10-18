from flask import Blueprint

bp = Blueprint('raw_materials', __name__)

from app.raw_materials import routes