"""Shared rate-limiter instance for atlas-api.

Defined here (rather than in main.py) so that route modules can import it
for per-endpoint decorators without creating circular imports.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from atlas_api.config import ApiConfig

_cfg = ApiConfig()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[_cfg.rate_limit_default],
    enabled=_cfg.rate_limit_enabled,
)
