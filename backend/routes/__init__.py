from .data_api import bp as data_api_bp
from .health import bp as health_bp
from .ranges import bp as ranges_bp
from .tiles import bp as tiles_bp
from .vrp import bp as vrp_bp


ALL_BLUEPRINTS = [health_bp, data_api_bp, ranges_bp, tiles_bp, vrp_bp]
