import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "operational"


@pytest.mark.asyncio
async def test_health_endpoint(client: AsyncClient):
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "database" in data


@pytest.mark.asyncio
async def test_create_and_redirect_url(client: AsyncClient):
    # 1. Create short URL
    create_payload = {
        "original_url": "https://www.heidelberg-university.de/en",
        "custom_code": "heidelberg",
    }
    create_res = await client.post("/api/v1/urls", json=create_payload)
    assert create_res.status_code == 201
    created_data = create_res.json()
    assert created_data["short_code"] == "heidelberg"
    assert created_data["original_url"] == "https://www.heidelberg-university.de/en"

    # 2. Redirect to original URL
    redirect_res = await client.get("/heidelberg", follow_redirects=False)
    assert redirect_res.status_code == 307
    assert redirect_res.headers["location"] == "https://www.heidelberg-university.de/en"

    # 3. Check Analytics
    analytics_res = await client.get("/api/v1/urls/heidelberg/analytics")
    assert analytics_res.status_code == 200
    analytics_data = analytics_res.json()
    assert analytics_data["total_clicks"] >= 1


@pytest.mark.asyncio
async def test_custom_code_conflict(client: AsyncClient):
    payload = {
        "original_url": "https://example.com/one",
        "custom_code": "unique-alias",
    }
    res1 = await client.post("/api/v1/urls", json=payload)
    assert res1.status_code == 201

    # Attempt to reuse the same alias
    payload2 = {
        "original_url": "https://example.com/two",
        "custom_code": "unique-alias",
    }
    res2 = await client.post("/api/v1/urls", json=payload2)
    assert res2.status_code == 409


@pytest.mark.asyncio
async def test_delete_short_url(client: AsyncClient):
    create_payload = {
        "original_url": "https://example.com/to-delete",
        "custom_code": "del-code",
    }
    await client.post("/api/v1/urls", json=create_payload)

    # Delete
    del_res = await client.delete("/api/v1/urls/del-code")
    assert del_res.status_code == 204

    # Resolve should 404
    get_res = await client.get("/del-code", follow_redirects=False)
    assert get_res.status_code == 404
