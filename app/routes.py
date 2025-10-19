from flask import Blueprint, redirect, url_for
from flask_login import login_required

# Use a different name for the blueprint to avoid conflicts, e.g., 'main'
main_bp = Blueprint('main', __name__)

@main_bp.route('/')
@login_required
def index():
    """Redirect the root URL to the dashboard."""
    return redirect(url_for('dashboard.index'))