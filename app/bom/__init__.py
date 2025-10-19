from flask import Blueprint

bp = Blueprint('bom', __name__)

from app.bom import routes