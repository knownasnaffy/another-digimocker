import base64
import hashlib
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

import store
import fixtures
from config import settings

router = APIRouter()
templates = Jinja2Templates(directory="templates")


def _verify_client(client_id: str | None, client_secret: str | None, request: Request) -> bool:
    """Check client credentials from Basic Auth or form params."""
    # Try HTTP Basic Auth first
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("basic "):
        try:
            decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
            cid, csecret = decoded.split(":", 1)
            return cid == settings.CLIENT_ID and csecret == settings.CLIENT_SECRET
        except Exception:
            return False

    # Fall back to form params
    return client_id == settings.CLIENT_ID and client_secret == settings.CLIENT_SECRET


# ---------------------------------------------------------------------------
# GET /public/oauth2/1/authorize — serve the consent page
# ---------------------------------------------------------------------------

@router.get("/public/oauth2/1/authorize", response_class=HTMLResponse)
async def authorize(
    request: Request,
    response_type: str = None,
    client_id: str = None,
    redirect_uri: str = None,
    state: str = "",
    code_challenge: str = None,
    code_challenge_method: str = None,
):
    # Validate client_id
    if client_id != settings.CLIENT_ID:
        if redirect_uri:
            return RedirectResponse(
                f"{redirect_uri}?error=unauthorized_client&state={state}"
            )
        raise HTTPException(status_code=400, detail="unauthorized_client")

    # Validate response_type
    if response_type != "code":
        if redirect_uri:
            return RedirectResponse(
                f"{redirect_uri}?error=unsupported_response_type&state={state}"
            )
        raise HTTPException(status_code=400, detail="unsupported_response_type")

    # Validate PKCE if enforced
    if settings.ENFORCE_PKCE and not code_challenge:
        if redirect_uri:
            return RedirectResponse(
                f"{redirect_uri}?error=invalid_request&error_description=code_challenge+required&state={state}"
            )
        raise HTTPException(status_code=400, detail="code_challenge required")

    persona_list = fixtures.list_personas()

    return templates.TemplateResponse(
        "consent.html",
        {
            "request": request,
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": code_challenge or "",
            "code_challenge_method": code_challenge_method or "",
            "personas": persona_list,
        },
    )


# ---------------------------------------------------------------------------
# POST /public/oauth2/1/authorize/callback — internal: handle consent form
# ---------------------------------------------------------------------------

@router.post("/public/oauth2/1/authorize/callback")
async def authorize_callback(
    persona_id: str = Form(...),
    redirect_uri: str = Form(...),
    state: str = Form(""),
    code_challenge: str = Form(""),
    action: str = Form("authorize"),
):
    if action == "deny":
        return RedirectResponse(
            f"{redirect_uri}?error=access_denied&error_description=User+denied+access&state={state}",
            status_code=302,
        )

    # Validate persona exists
    persona = fixtures.get_persona(persona_id)
    if not persona:
        raise HTTPException(status_code=400, detail="Unknown persona_id")

    code = secrets.token_hex(20)
    store.auth_codes[code] = {
        "persona_id": persona_id,
        "redirect_uri": redirect_uri,
        "code_challenge": code_challenge,
        "expires_at": datetime.utcnow() + timedelta(seconds=300),
    }

    return RedirectResponse(
        f"{redirect_uri}?code={code}&state={state}",
        status_code=302,
    )


# ---------------------------------------------------------------------------
# POST /public/oauth2/1/token
# ---------------------------------------------------------------------------

@router.post("/public/oauth2/1/token")
async def token(
    request: Request,
    grant_type: str = Form(...),
    code: str = Form(None),
    redirect_uri: str = Form(None),
    client_id: str = Form(None),
    client_secret: str = Form(None),
    code_verifier: str = Form(None),
    refresh_token: str = Form(None),
):
    if not _verify_client(client_id, client_secret, request):
        return _token_error("invalid_client", "Client authentication failed")

    if grant_type == "authorization_code":
        return _handle_auth_code(code, redirect_uri, code_verifier)
    elif grant_type == "refresh_token":
        return _handle_refresh_token(refresh_token)
    else:
        return _token_error("invalid_grant_type", f"Unsupported grant_type: {grant_type}")


def _handle_auth_code(code: str, redirect_uri: str, code_verifier: str):
    entry = store.auth_codes.get(code)
    if not entry:
        return _token_error("invalid_grant", "The authorization code is invalid or has expired")

    if datetime.utcnow() > entry["expires_at"]:
        del store.auth_codes[code]
        return _token_error("invalid_grant", "The authorization code is invalid or has expired")

    if settings.ENFORCE_PKCE:
        stored_challenge = entry.get("code_challenge", "")
        if not code_verifier or not stored_challenge:
            return _token_error("invalid_grant", "code_verifier required")
        computed = base64.urlsafe_b64encode(
            hashlib.sha256(code_verifier.encode()).digest()
        ).rstrip(b"=").decode()
        if computed != stored_challenge:
            return _token_error("invalid_grant", "code_verifier mismatch")

    if redirect_uri != entry["redirect_uri"]:
        return _token_error("invalid_grant", "redirect_uri mismatch")

    persona_id = entry["persona_id"]
    del store.auth_codes[code]

    persona = fixtures.get_persona(persona_id)
    if not persona:
        return _token_error("invalid_grant", "Persona not found")

    token_data = store.issue_token_pair(persona_id)
    token_data.update({
        "digilockerid": persona["digilockerid"],
        "name": persona["name"],
        "dob": persona["dob"],
        "gender": persona["gender"],
        "eaadhaar": persona["eaadhaar"],
        "new_account": "N",
        "reference_key": persona["reference_key"],
    })
    return token_data


def _handle_refresh_token(refresh_token: str):
    entry = store.refresh_tokens.get(refresh_token)
    if not entry:
        return _token_error("invalid_grant", "The refresh token is invalid or has expired")

    if datetime.utcnow() > entry["expires_at"]:
        del store.refresh_tokens[refresh_token]
        return _token_error("invalid_grant", "The refresh token is invalid or has expired")

    persona_id = entry["persona_id"]
    del store.refresh_tokens[refresh_token]

    persona = fixtures.get_persona(persona_id)
    if not persona:
        return _token_error("invalid_grant", "Persona not found")

    token_data = store.issue_token_pair(persona_id)
    token_data.update({
        "digilockerid": persona["digilockerid"],
        "name": persona["name"],
        "dob": persona["dob"],
        "gender": persona["gender"],
        "eaadhaar": persona["eaadhaar"],
        "reference_key": persona["reference_key"],
    })
    return token_data


def _token_error(error: str, description: str):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=400,
        content={"error": error, "error_description": description},
    )


# ---------------------------------------------------------------------------
# POST /public/oauth2/1/revoke
# ---------------------------------------------------------------------------

@router.post("/public/oauth2/1/revoke")
async def revoke(
    request: Request,
    token: str = Form(...),
    token_type_hint: str = Form(None),
):
    # Real spec returns 200 regardless — we do the same
    store.access_tokens.pop(token, None)
    store.refresh_tokens.pop(token, None)
    return {}
