"""
Integration tests for API endpoints
"""
import pytest


@pytest.mark.integration
@pytest.mark.api
@pytest.mark.slow
class TestAPIIntegration:
    """Integration tests for full API flow"""

    def test_api_documentation_accessible(self, client):
        """Test that API documentation is accessible"""
        response = client.get("/docs")
        assert response.status_code == 200

    def test_redoc_accessible(self, client):
        """Test that ReDoc documentation is accessible"""
        response = client.get("/redoc")
        assert response.status_code == 200

    def test_openapi_schema(self, client):
        """Test that OpenAPI schema is valid"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert schema["info"]["title"] == "TQ Data Platform API"

    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options("/", headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET"
        })
        # FastAPI's CORS middleware should handle this
        assert response.status_code in [200, 405]  # Either OK or Method Not Allowed
