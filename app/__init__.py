from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_caching import Cache
import os
import logging
from logging.handlers import RotatingFileHandler

# Import your timezone utility functions
from app.utils.timezone import format_local_date, format_local_datetime, format_local_time

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
csrf = CSRFProtect()
limiter = Limiter(key_func=get_remote_address)
cache = Cache()

def create_app(config_class=None):
    app = Flask(__name__)
    
    # Load configuration
    if config_class is None:
        from config import Config
        config_class = Config
    
    app.config.from_object(config_class)
    
    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)
    
    # Register Jinja filters for timezone formatting
    app.jinja_env.filters['local_date'] = format_local_date
    app.jinja_env.filters['local_datetime'] = format_local_datetime
    app.jinja_env.filters['local_time'] = format_local_time
    
    # Configure login manager
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please log in to access this page.'
    login_manager.login_message_category = 'info'
    
    # Register blueprints
    from app.auth import bp as auth_bp
    app.register_blueprint(auth_bp, url_prefix='/auth')
    
    from app.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    
    from app.products import bp as products_bp
    app.register_blueprint(products_bp, url_prefix='/products')
    
    from app.raw_materials import bp as raw_materials_bp
    app.register_blueprint(raw_materials_bp, url_prefix='/raw-materials')
    
    from app.bom import bp as bom_bp
    app.register_blueprint(bom_bp, url_prefix='/bom')
    
    from app.sales import bp as sales_bp
    app.register_blueprint(sales_bp, url_prefix='/sales')
    
    from app.customers import bp as customers_bp
    app.register_blueprint(customers_bp, url_prefix='/customers')
    
    from app.marketplace import bp as marketplace_bp
    app.register_blueprint(marketplace_bp, url_prefix='/marketplace')
    
    from app.reports import bp as reports_bp
    app.register_blueprint(reports_bp, url_prefix='/reports')
    
    from app.settings import bp as settings_bp
    app.register_blueprint(settings_bp, url_prefix='/settings')
    
    from app.superadmin import bp as superadmin_bp
    app.register_blueprint(superadmin_bp, url_prefix='/superadmin')
    
    # Register main routes blueprint
    from app.routes import main_bp
    app.register_blueprint(main_bp)
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('errors/403.html'), 403
    
    # Configure logging
    if not app.debug and not app.testing:
        if not os.path.exists('logs'):
            os.mkdir('logs')
        file_handler = RotatingFileHandler('logs/posrss.log', maxBytes=10240, backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('POS RSS startup')
    
    return app

from app import models