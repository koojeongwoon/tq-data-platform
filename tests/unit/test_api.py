"""
Unit tests for FastAPI endpoints
"""
import pytest
from fastapi import status


@pytest.mark.unit
@pytest.mark.api
class TestAPIEndpoints:
    """Test API endpoint functionality"""

    def test_root_endpoint(self, client):
        """Test root endpoint returns correct response"""
        response = client.get("/")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["message"] == "TQ Data Platform API"
        assert "version" in data
        assert data["status"] == "running"

    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"

    def test_welfare_policies_list(self, client, mock_d1_client):
        """Test welfare policies list endpoint"""
        # Mock successful response
        mock_d1_client.execute_query = lambda q: {
            "results": [
                {
                    "policy_id": "TEST001",
                    "policy_name": "테스트 정책",
                    "policy_summary": "테스트 요약"
                }
            ]
        }

        response = client.get("/welfare/policies")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "policies" in data
        assert "total" in data

    def test_welfare_policies_pagination(self, client, mock_d1_client):
        """Test welfare policies pagination"""
        response = client.get("/welfare/policies?limit=50&offset=10")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["limit"] == 50
        assert data["offset"] == 10

    def test_welfare_policy_detail(self, client, mock_d1_client):
        """Test welfare policy detail endpoint"""
        policy_id = "TEST001"

        # Mock successful response
        mock_d1_client.execute_query = lambda q: {
            "results": [
                {
                    "policy_id": policy_id,
                    "policy_name": "테스트 정책",
                    "policy_summary": "테스트 요약"
                }
            ]
        }

        response = client.get(f"/welfare/policies/{policy_id}")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["policy_id"] == policy_id

    def test_welfare_policy_not_found(self, client, mock_d1_client):
        """Test welfare policy not found"""
        # Mock empty response
        mock_d1_client.execute_query = lambda q: {"results": []}

        response = client.get("/welfare/policies/NONEXISTENT")
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_welfare_stats(self, client, mock_d1_client):
        """Test welfare stats endpoint"""
        # Mock stats response
        def mock_query(q):
            if "COUNT" in q:
                return {"results": [{"total": 100}]}
            elif "MAX" in q:
                return {"results": [{"latest": "2024-01-01"}]}
            return {"results": []}

        mock_d1_client.execute_query = mock_query

        response = client.get("/welfare/stats")
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "total_policies" in data
        assert "latest_update" in data
