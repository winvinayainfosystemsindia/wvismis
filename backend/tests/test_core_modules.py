"""End-to-end tests for Authentication, Multi-Tenancy (Organizations), Users, OpenAPI, and AI Harness"""

import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_root_and_openapi_docs(client: AsyncClient):
    """Verify root metadata and OpenAPI JSON schema generation"""
    root_res = await client.get("/")
    assert root_res.status_code == 200
    data = root_res.json()
    assert data["api_v1"] == "/api/v1"
    assert data["openapi"] == "/openapi.json"

    openapi_res = await client.get("/openapi.json")
    assert openapi_res.status_code == 200
    schema = openapi_res.json()
    assert "/api/v1/auth/login" in schema["paths"]
    assert "/api/v1/auth/verify" in schema["paths"]
    assert "/api/v1/organizations/current" in schema["paths"]
    assert "/api/v1/users/" in schema["paths"]
    assert "/api/v1/ai/run" in schema["paths"]
    assert "/api/v1/ws/broadcast" in schema["paths"]


@pytest.mark.anyio
async def test_auth_lifecycle_and_multitenancy(client: AsyncClient, test_user_data: dict):
    """Test registration (auto-creating tenant organization), login, verify token, refresh rotation, and logout"""
    # 1. Register user + new tenant organization
    reg_res = await client.post("/api/v1/auth/register", json=test_user_data)
    assert reg_res.status_code == 201
    user = reg_res.json()
    assert user["email"] == test_user_data["email"]
    assert user["role"] == "org_admin"
    assert user["organization"]["slug"] == "winvinaya"

    # 2. Login
    login_res = await client.post(
        "/api/v1/auth/login",
        json={
            "email": test_user_data["email"],
            "password": test_user_data["password"],
            "organization_slug": "winvinaya",
        },
    )
    assert login_res.status_code == 200
    tokens = login_res.json()
    access_token = tokens["access_token"]
    refresh_token = tokens["refresh_token"]
    assert tokens["organization_id"] == user["organization_id"]

    # 3. Verify Access Token
    verify_res = await client.post(
        "/api/v1/auth/verify",
        json={"token": access_token, "token_type": "access"},
    )
    assert verify_res.status_code == 200
    v_data = verify_res.json()
    assert v_data["valid"] is True
    assert v_data["user_id"] == user["id"]
    assert v_data["organization_id"] == user["organization_id"]

    # 4. Fetch Current Organization & Stats
    headers = {"Authorization": f"Bearer {access_token}"}
    org_res = await client.get("/api/v1/organizations/current", headers=headers)
    assert org_res.status_code == 200
    assert org_res.json()["slug"] == "winvinaya"

    stats_res = await client.get("/api/v1/organizations/current/stats", headers=headers)
    assert stats_res.status_code == 200
    assert stats_res.json()["active_users"] == 1

    # 5. Create another user inside the same Organization
    create_u_res = await client.post(
        "/api/v1/users/",
        headers=headers,
        json={
            "email": "member@winvinaya.com",
            "username": "wvmember",
            "password": "MemberPass123",
            "full_name": "Team Member",
            "role": "manager",
            "department": "Engineering",
        },
    )
    assert create_u_res.status_code == 201
    member = create_u_res.json()
    assert member["organization_id"] == user["organization_id"]

    # 6. List Users in Organization
    users_res = await client.get("/api/v1/users/", headers=headers)
    assert users_res.status_code == 200
    assert users_res.json()["total"] == 2

    # 7. Test Harness Agentic AI Tools & Direct Execution
    tools_res = await client.get("/api/v1/ai/tools", headers=headers)
    assert tools_res.status_code == 200
    tool_names = [t["name"] for t in tools_res.json()]
    assert "get_organization_overview" in tool_names
    assert "search_organization_users" in tool_names

    exec_res = await client.post(
        "/api/v1/ai/tools/get_organization_overview/execute",
        headers=headers,
        json={},
    )
    assert exec_res.status_code == 200
    assert exec_res.json()["success"] is True
    assert exec_res.json()["data"]["total_users"] == 2

    # 8. Refresh Token Rotation
    refresh_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == 200
    new_tokens = refresh_res.json()
    assert new_tokens["access_token"] != access_token

    # Old refresh token should now be blacklisted
    replay_res = await client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert replay_res.status_code == 401

    # 9. Logout revokes access token
    new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
    logout_res = await client.post(
        "/api/v1/auth/logout",
        headers=new_headers,
        json={"refresh_token": new_tokens["refresh_token"]},
    )
    assert logout_res.status_code == 200

    # Verify revoked token is rejected
    me_after_logout = await client.get("/api/v1/users/me", headers=new_headers)
    assert me_after_logout.status_code == 401
