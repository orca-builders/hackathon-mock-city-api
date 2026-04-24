from __future__ import annotations

import hashlib
import os
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ORCA_API_URL = os.environ.get(
    "ORCA_API_URL", "https://hacketon-18march-api.orcapt.com/api/v1/external"
).rstrip("/")
ORCA_WORKSPACE_TOKEN = os.environ.get("ORCA_WORKSPACE_TOKEN", "")
ORCA_TENANT = os.environ.get("ORCA_TENANT", "hacketon-18march")

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    first_name: str = Field(..., min_length=1)
    last_name: str = Field(..., min_length=1)
    email: str = Field(..., min_length=1)
    team: str = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def team_to_department(team: str) -> tuple[str, str]:
    """Map team name to (external_id, name). Team 1 -> team-1, Team 2 -> team-2, etc."""
    mapping = {f"Team {i}": f"team-{i}" for i in range(1, 7)}
    external_id = mapping.get(team, f"team-{team.lower().replace(' ', '-')}")
    return (external_id, team)


def user_external_id(email: str) -> str:
    """Generate stable external_id from email."""
    h = hashlib.sha256(email.lower().strip().encode()).hexdigest()[:16]
    return f"usr-{h}"


async def orca_request(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    json: Optional[dict] = None,
) -> httpx.Response:
    """Make request to Orca API."""
    url = f"{ORCA_API_URL}/{path.lstrip('/')}"
    headers = {
        "X-Workspace": ORCA_WORKSPACE_TOKEN,
        "X-Tenant": ORCA_TENANT,
        "Content-Type": "application/json",
    }
    return await client.request(method, url, headers=headers, json=json)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Registration API",
    description="Register users in Orca and assign to departments (teams)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/register")
async def register(data: RegisterRequest):
    if not ORCA_WORKSPACE_TOKEN:
        raise HTTPException(
            status_code=500,
            detail="Registration service not configured (missing ORCA_WORKSPACE_TOKEN)",
        )

    dep_external_id, _ = team_to_department(data.team)
    user_ext_id = user_external_id(data.email)

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
        # 1. Create user (departments team-1..team-6 already exist)
        user_resp = await orca_request(
            client,
            "POST",
            "/users",
            json={
                "external_id": user_ext_id,
                "email": data.email.strip().lower(),
                "first_name": data.first_name.strip(),
                "last_name": data.last_name.strip(),
                "role": "superadmin",
            },
        )
        if user_resp.status_code in (409, 400):
            body = user_resp.json() if user_resp.text else {}
            err = body.get("detail", body.get("message", user_resp.text))
            if "already" in str(err).lower() or user_resp.status_code == 409:
                raise HTTPException(
                    status_code=409,
                    detail="This email is already registered",
                )
            raise HTTPException(status_code=400, detail=err or "User creation failed")
        if user_resp.status_code not in (200, 201):
            raise HTTPException(
                status_code=502,
                detail=f"Orca user creation failed: {user_resp.text}",
            )

        # 2. Assign user to department (team-1..team-6)
        assign_resp = await orca_request(
            client,
            "POST",
            "/assign-user-department",
            json={
                "user_external_id": user_ext_id,
                "department_external_ids": [dep_external_id],
            },
        )
        if assign_resp.status_code not in (200, 201, 204):
            raise HTTPException(
                status_code=502,
                detail=f"Orca assignment failed: {assign_resp.text}",
            )

    return {"status": "ok", "message": "Registered successfully"}


@app.get("/health")
def health():
    return {"status": "ok"}
