import pytest
import os
import uuid
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["POSTGRES_DB"] = "superactive"
os.environ["DISABLE_TELEMETRY"] = "1"

def _sync_insert_call(tenant_id: str, agent_id: str, call_id: str, days_ago: int, outcome: str, hang_up_state: str = None, duration: int = 60, cost: float = 0.05):
    """Insert a fake call into PostgreSQL directly."""
    import psycopg2
    dsn = (
        f"host={os.environ.get('POSTGRES_HOST', 'localhost')} "
        f"port={os.environ.get('POSTGRES_PORT', '5432')} "
        f"dbname={os.environ.get('POSTGRES_DB', 'superactive')} "
        f"user={os.environ.get('POSTGRES_USER', 'superactive')} "
        f"password={os.environ.get('POSTGRES_PASSWORD', 'superactive')}"
    )
    conn = psycopg2.connect(dsn)
    try:
        started_at = datetime.now() - timedelta(days=days_ago)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO calls (call_id, tenant_id, agent_id, started_at, ended_at, duration_seconds, outcome, hang_up_state, cost_estimate) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT DO NOTHING",
                (call_id, tenant_id, agent_id, started_at, started_at + timedelta(seconds=duration), duration, outcome, hang_up_state, cost),
            )
        conn.commit()
    finally:
        conn.close()

@pytest.fixture
def app():
    from server import app
    app.state.limiter.enabled = False
    return app

@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient
    with TestClient(app) as c:
        yield c

class TestIntegrationAnalytics:
    """End-to-end test for Sprint 4 Analytics Data and Date Filtering."""

    def test_analytics_date_filtering(self, client):
        # 1. Register a new user to isolate data
        unique_id = str(uuid.uuid4())
        email = f"analytics_test_{unique_id}@superactive.ai"
        password = "SecurePassword123!"

        reg_res = client.post("/api/auth/register", json={
            "email": email, "password": password, "business_name": "Analytics Corp"
        })
        assert reg_res.status_code == 200

        login_res = client.post("/api/auth/login", json={"email": email, "password": password})
        assert login_res.status_code == 200

        me_res = client.get("/api/auth/me")
        tenant_id = me_res.json()["tenant_id"]

        agent_id = f"test_agent_{unique_id}"

        # 2. Insert test calls
        # 2 calls today (booked, completed)
        _sync_insert_call(tenant_id, agent_id, f"call_{uuid.uuid4()}", days_ago=0, outcome="booked", duration=120, cost=0.10)
        _sync_insert_call(tenant_id, agent_id, f"call_{uuid.uuid4()}", days_ago=0, outcome="completed", duration=60, cost=0.05)
        
        # 1 call 3 days ago (hung_up in 'qualifying')
        _sync_insert_call(tenant_id, agent_id, f"call_{uuid.uuid4()}", days_ago=3, outcome="hung_up", hang_up_state="qualifying", duration=30, cost=0.02)
        
        # 1 call 10 days ago (transferred)
        _sync_insert_call(tenant_id, agent_id, f"call_{uuid.uuid4()}", days_ago=10, outcome="transferred", duration=300, cost=0.25)

        # 1 call 40 days ago (should not appear in 30-day window)
        _sync_insert_call(tenant_id, agent_id, f"call_{uuid.uuid4()}", days_ago=40, outcome="booked", duration=100, cost=0.10)

        # 3. Test GET /api/analytics with default (30 days)
        res_30 = client.get("/api/analytics")
        assert res_30.status_code == 200
        data_30 = res_30.json()

        assert data_30["total_calls"] == 4, "Should find 4 calls in last 30 days"
        assert data_30["outcomes"]["booked"] == 1
        assert data_30["outcomes"]["hung_up"] == 1
        assert data_30["total_cost"] == 0.42 # 0.10 + 0.05 + 0.02 + 0.25
        assert data_30["avg_cost_per_call"] == 0.105
        assert "qualifying" in data_30["hang_up_heatmap"]
        assert data_30["hang_up_heatmap"]["qualifying"] == 1
        
        # calls_per_day should be exactly 30 days long
        assert len(data_30["calls_per_day"]) == 30
        today_str = datetime.now().strftime("%Y-%m-%d")
        today_data = next((c for c in data_30["calls_per_day"] if c["date"] == today_str), None)
        assert today_data is not None
        assert today_data["count"] == 2

        # 4. Test GET /api/analytics?days=7
        res_7 = client.get("/api/analytics?days=7")
        assert res_7.status_code == 200
        data_7 = res_7.json()

        assert data_7["total_calls"] == 3, "Should find 3 calls in last 7 days"
        assert len(data_7["calls_per_day"]) == 7
        assert data_7["total_cost"] == 0.17 # 0.10 + 0.05 + 0.02

        # 5. Test GET /api/analytics?days=60
        res_60 = client.get("/api/analytics?days=60")
        assert res_60.status_code == 200
        data_60 = res_60.json()

        assert data_60["total_calls"] == 5, "Should find all 5 calls in last 60 days"
        assert data_60["outcomes"]["booked"] == 2

        # 6. Cleanup history
        del_res = client.delete("/api/analytics/history")
        assert del_res.status_code == 200

        res_empty = client.get("/api/analytics")
        assert res_empty.json()["total_calls"] == 0
