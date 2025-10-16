from flask import Blueprint

bp = Blueprint('superadmin', __name__, template_folder='templates')

from . import routes
