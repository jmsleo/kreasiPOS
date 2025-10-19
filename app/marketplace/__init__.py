from flask import Blueprint

bp = Blueprint('marketplace', __name__, template_folder='templates')

from . import routes, forms
