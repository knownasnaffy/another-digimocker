from fastapi import FastAPI

import fixtures
import store
from routers import oauth, user, files

app = FastAPI(title="DigiLocker Mock Server", version="1.0.0")

# Load personas at startup — fails fast if file is missing or malformed
fixtures.load_personas()

# Register API routers
app.include_router(oauth.router)
app.include_router(user.router)
app.include_router(files.router)


# ---------------------------------------------------------------------------
# Mock control endpoints (/mock/*)
# ---------------------------------------------------------------------------

@app.get("/mock/health")
async def health():
    return {"status": "ok"}


@app.get("/mock/personas")
async def mock_personas():
    return fixtures.list_personas()


@app.post("/mock/reset")
async def mock_reset():
    store.clear_all()
    return {"message": "State cleared"}


@app.post("/mock/token/direct")
async def mock_token_direct(body: dict):
    persona_id = body.get("persona_id")
    if not persona_id:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=400,
            content={"error": "missing_persona_id", "error_description": "persona_id is required"},
        )

    persona = fixtures.get_persona(persona_id)
    if not persona:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"error": "not_found", "error_description": f"No persona with id '{persona_id}'"},
        )

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
