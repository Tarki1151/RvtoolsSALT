# Routes package - All blueprints
from .core import core_bp
from .vms import vms_bp
from .datastores import datastores_bp
from .risks import risks_bp
from .dr import dr_bp
from .hosts import hosts_bp
from .reports import reports_bp
from .optimization import optimization_bp

__all__ = [
    'core_bp',
    'vms_bp',
    'datastores_bp',
    'risks_bp', 
    'dr_bp',
    'hosts_bp',
    'reports_bp',
    'optimization_bp'
]
