"""
Superactive — Route Registration

Import all route modules and expose them for the main app.
"""

from routes.agents import router as agents_router
from routes.calls import router as calls_router
from routes.campaigns import router as campaigns_router
from routes.telephony import router as telephony_router

all_routers = [
    agents_router,
    calls_router,
    campaigns_router,
    telephony_router,
]
