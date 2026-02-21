"""
Superactive — Route Registration

Import all route modules and expose them for the main app.
"""

from routes.agents import router as agents_router
from routes.auth import router as auth_router
from routes.calls import router as calls_router
from routes.campaigns import router as campaigns_router
from routes.health import router as health_router
from routes.settings import router as settings_router
from routes.telephony import router as telephony_router
from routes.monitor import router as monitor_router

all_routers = [
    health_router,
    auth_router,
    agents_router,
    calls_router,
    campaigns_router,
    settings_router,
    telephony_router,
    monitor_router,
]

