"""
Configuration Management for ACI Analysis Tool
"""
import os
import secrets
from pathlib import Path


class Config:
    """Base configuration"""

    # Base directories
    BASE_DIR = Path(__file__).parent
    DATA_DIR = BASE_DIR / 'data'
    FABRICS_DIR = BASE_DIR / 'fabrics'
    CMDB_DIR = BASE_DIR / 'cmdb'
    OUTPUT_DIR = BASE_DIR / 'output'

    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY')
    MAX_CONTENT_LENGTH = int(os.environ.get('MAX_UPLOAD_SIZE', 100 * 1024 * 1024))  # 100MB default

    # Session configuration
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = 3600  # 1 hour

    # EVPN configuration
    L3_VNI_START = int(os.environ.get('L3_VNI_START', 50000))
    L2_VNI_START = int(os.environ.get('L2_VNI_START', 10000))
    VLAN_START = int(os.environ.get('VLAN_START', 100))

    # File upload restrictions
    ALLOWED_EXTENSIONS = {'json', 'xml', 'csv', 'txt', 'cfg', 'conf'}
    ALLOWED_CONTENT_TYPES = {
        'json': ['application/json', 'text/plain'],
        'xml': ['application/xml', 'text/xml', 'text/plain'],
        'csv': ['text/csv', 'text/plain'],
        'txt': ['text/plain'],
        'cfg': ['text/plain'],
        'conf': ['text/plain']
    }

    # Logging configuration
    LOG_FILE = BASE_DIR / 'aci_tool.log'
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_MAX_BYTES = 10 * 1024 * 1024  # 10MB
    LOG_BACKUP_COUNT = 5

    # Cache configuration
    CACHE_TIMEOUT = int(os.environ.get('CACHE_TIMEOUT', 300))  # 5 minutes

    # API configuration
    API_RATE_LIMIT = os.environ.get('API_RATE_LIMIT', '200 per day, 50 per hour')

    @staticmethod
    def init_app(app):
        """Initialize application configuration"""
        # Ensure directories exist
        for directory in [Config.DATA_DIR, Config.FABRICS_DIR,
                         Config.CMDB_DIR, Config.OUTPUT_DIR]:
            directory.mkdir(exist_ok=True)

        # Validate secret key
        if not Config.SECRET_KEY:
            if app.debug:
                # Generate a temporary secret key for development
                Config.SECRET_KEY = secrets.token_hex(32)
                app.logger.warning(
                    "Using auto-generated SECRET_KEY for development. "
                    "Set SECRET_KEY environment variable for production!"
                )
            else:
                raise RuntimeError(
                    "SECRET_KEY environment variable must be set in production. "
                    "Generate one using: python -c 'import secrets; print(secrets.token_hex(32))'"
                )


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True  # Require HTTPS

    @staticmethod
    def init_app(app):
        Config.init_app(app)

        # Production-specific validations
        if not os.environ.get('SECRET_KEY'):
            raise RuntimeError("SECRET_KEY must be set in production")


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = True
    TESTING = True
    SECRET_KEY = 'test-secret-key-for-testing-only'
    WTF_CSRF_ENABLED = False  # Disable CSRF for testing


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}


def get_config(config_name=None):
    """Get configuration object based on environment"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    return config.get(config_name, config['default'])
