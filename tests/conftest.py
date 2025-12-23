"""
Pytest configuration and fixtures
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from shared.db.d1 import D1Client


@pytest.fixture
def client():
    """FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def mock_d1_client(monkeypatch):
    """Mock D1Client for testing without actual API calls"""
    class MockD1Client:
        def __init__(self):
            self.queries_executed = []

        def execute_query(self, query):
            self.queries_executed.append(query)
            return {
                "results": [],
                "success": True
            }

        def execute_batch(self, queries):
            self.queries_executed.extend(queries)
            return {
                "results": [],
                "success": True
            }

        def init_db(self):
            pass

    mock_client = MockD1Client()
    monkeypatch.setattr("shared.db.d1.D1Client", lambda: mock_client)
    return mock_client


@pytest.fixture
def sample_policy_data():
    """Sample welfare policy data for testing"""
    return {
        "policy_id": "TEST001",
        "policy_name": "테스트 복지 정책",
        "policy_summary": "테스트용 복지 정책 요약",
        "target_audience": "청년",
        "support_details": "월 50만원 지원",
        "application_method": "온라인 신청"
    }


@pytest.fixture
def sample_xml_response():
    """Sample XML response from Public Data Portal API"""
    return '''<?xml version="1.0" encoding="UTF-8"?>
<response>
    <header>
        <resultCode>00</resultCode>
        <resultMsg>NORMAL SERVICE</resultMsg>
    </header>
    <body>
        <items>
            <item>
                <servId>TEST001</servId>
                <servNm>테스트 복지 정책</servNm>
                <servDgst>테스트용 복지 정책 요약</servDgst>
            </item>
        </items>
    </body>
</response>'''


@pytest.fixture(autouse=True)
def reset_environment(monkeypatch):
    """Reset environment variables for each test"""
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "test-account-id")
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "test-api-token")
    monkeypatch.setenv("CLOUDFLARE_D1_DB_ID", "test-db-id")
