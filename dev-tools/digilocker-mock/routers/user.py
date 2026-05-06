from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

import store
import fixtures

router = APIRouter()


def _resolve_token(request: Request):
    """Extract and resolve Bearer token from Authorization header."""
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None, _token_error()
    token = auth[7:]
    entry = store.resolve_access_token(token)
    if not entry:
        return None, _token_error()
    return entry, None


def _token_error():
    return JSONResponse(
        status_code=401,
        content={
            "error": "invalid_token",
            "error_description": "The access token is invalid or has expired",
        },
    )


# ---------------------------------------------------------------------------
# GET /public/oauth2/1/user
# ---------------------------------------------------------------------------

@router.get("/public/oauth2/1/user")
async def get_user(request: Request):
    entry, err = _resolve_token(request)
    if err:
        return err

    persona = fixtures.get_persona(entry["persona_id"])
    if not persona:
        return _token_error()

    return {
        "digilockerid": persona["digilockerid"],
        "name": persona["name"],
        "dob": persona["dob"],
        "gender": persona["gender"],
        "eaadhaar": persona["eaadhaar"],
        "reference_key": persona["reference_key"],
    }
