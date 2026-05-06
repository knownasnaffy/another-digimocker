import os
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse

from fastapi import APIRouter, Form, Request
from fastapi.responses import JSONResponse, Response
from jinja2 import Environment, FileSystemLoader

import store
import fixtures

router = APIRouter()

# Jinja2 env for XML templates
_xml_template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "xml_templates")
_jinja_env = Environment(loader=FileSystemLoader(_xml_template_dir), autoescape=False)


def _resolve_token(request: Request):
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None, _token_error()
    token_str = auth[7:]
    entry = store.resolve_access_token(token_str)
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


def _dl_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to DD-MM-YYYY for issued docs list."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        return d.strftime("%d-%m-%Y")
    except Exception:
        return date_str


# ---------------------------------------------------------------------------
# GET /public/oauth2/2/files/issued
# ---------------------------------------------------------------------------

@router.get("/public/oauth2/2/files/issued")
async def files_issued(request: Request):
    entry, err = _resolve_token(request)
    if err:
        return err

    persona = fixtures.get_persona(entry["persona_id"])
    if not persona:
        return _token_error()

    items = []
    dl = persona.get("driving_license")
    if dl:
        items.append({
            "name": "Driving License",
            "type": "file",
            "size": "1024",
            "date": _dl_date(dl["issue_date"]),
            "parent": "issueddocs",
            "mime": "application/xml",
            "uri": f"https://mock-digilocker/xml/DL/{dl['dl_number']}",
            "doctype": "DRVLC",
            "issuerid": "MOTRH",
            "description": "Driving License issued by Ministry of Road Transport and Highways",
            "issuer": "Ministry of Road Transport and Highways",
        })

    for vehicle in persona.get("vehicles", []):
        items.append({
            "name": f"Vehicle Registration Certificate - {vehicle['rc_number']}",
            "type": "file",
            "size": "1024",
            "date": _dl_date(vehicle["reg_date"]),
            "parent": "issueddocs",
            "mime": "application/xml",
            "uri": f"https://mock-digilocker/xml/RC/{vehicle['rc_number']}",
            "doctype": "VEHRC",
            "issuerid": "MOTRH",
            "description": "Vehicle Registration Certificate",
            "issuer": "Ministry of Road Transport and Highways",
        })

    return {"items": items}


# ---------------------------------------------------------------------------
# GET /public/oauth2/3/xml/files?uri=<encoded_uri>
# ---------------------------------------------------------------------------

@router.get("/public/oauth2/3/xml/files")
async def xml_files(request: Request, uri: str):
    entry, err = _resolve_token(request)
    if err:
        return err

    persona = fixtures.get_persona(entry["persona_id"])
    if not persona:
        return _token_error()

    # Parse uri: https://mock-digilocker/xml/{DL|RC}/{identifier}
    parsed = urlparse(uri)
    path_parts = parsed.path.strip("/").split("/")
    # Expected: ['xml', 'DL'|'RC', identifier]
    if len(path_parts) != 3 or path_parts[0] != "xml":
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_uri", "error_description": "Cannot parse document URI"},
        )

    doc_type = path_parts[1].upper()
    identifier = path_parts[2]

    if doc_type == "DL":
        dl = persona.get("driving_license")
        if not dl or dl["dl_number"] != identifier:
            return JSONResponse(
                status_code=404,
                content={"error": "document_not_found", "error_description": "Document not found for this user"},
            )
        xml_content = _render_dl_xml(persona, dl)
    elif doc_type == "RC":
        vehicle = next(
            (v for v in persona.get("vehicles", []) if v["rc_number"] == identifier),
            None,
        )
        if not vehicle:
            return JSONResponse(
                status_code=404,
                content={"error": "document_not_found", "error_description": "Document not found for this user"},
            )
        xml_content = _render_rc_xml(vehicle)
    else:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_uri", "error_description": f"Unknown document type: {doc_type}"},
        )

    return Response(content=xml_content, media_type="application/xml")


def _render_dl_xml(persona: dict, dl: dict) -> str:
    tmpl = _jinja_env.get_template("driving_license.xml")
    return tmpl.render(
        issuing_authority=dl["issuing_authority"],
        issue_date=dl["issue_date"],
        expiry_date=dl["expiry_date"],
        dl_number=dl["dl_number"],
        state=dl["state"],
        name=persona["name"],
        dob=persona["dob"],
        gender=persona["gender"],
        vehicle_classes=dl["vehicle_classes"],
        status=dl["status"],
    )


def _render_rc_xml(vehicle: dict) -> str:
    tmpl = _jinja_env.get_template("vehicle_rc.xml")
    return tmpl.render(**vehicle)


# ---------------------------------------------------------------------------
# POST /public/oauth2/1/pulldocument
# ---------------------------------------------------------------------------

@router.post("/public/oauth2/1/pulldocument")
async def pull_document(request: Request):
    entry, err = _resolve_token(request)
    if err:
        return err

    persona = fixtures.get_persona(entry["persona_id"])
    if not persona:
        return _token_error()

    try:
        body = await request.json()
    except Exception:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_request", "error_description": "Request body must be JSON"},
        )

    consent = body.get("consent", "")
    if consent != "Y":
        return JSONResponse(
            status_code=400,
            content={"error": "consent_required", "error_description": "User consent is required"},
        )

    doctype = body.get("doctype", "")
    parameters = body.get("parameters", [])

    valid_until = (
        datetime.now(tz=timezone(timedelta(hours=5, minutes=30))) + timedelta(days=365)
    ).strftime("%Y-%m-%dT%H:%M:%S+05:30")

    if doctype == "DRVLC":
        dl = persona.get("driving_license")
        if not dl:
            return JSONResponse(
                status_code=404,
                content={"error": "document_not_found", "error_description": "Driving license not found"},
            )
        return {
            "uri": f"https://mock-digilocker/xml/DL/{dl['dl_number']}",
            "validUpto": valid_until,
            "doctype": "DRVLC",
            "issuerid": "MOTRH",
        }
    elif doctype == "VEHRC":
        reg_no = next(
            (p["value"] for p in parameters if p.get("name") == "regNo"),
            None,
        )
        vehicle = next(
            (v for v in persona.get("vehicles", []) if v["rc_number"] == reg_no),
            None,
        )
        if not vehicle:
            return JSONResponse(
                status_code=404,
                content={"error": "document_not_found", "error_description": "Vehicle RC not found"},
            )
        return {
            "uri": f"https://mock-digilocker/xml/RC/{vehicle['rc_number']}",
            "validUpto": valid_until,
            "doctype": "VEHRC",
            "issuerid": "MOTRH",
        }
    else:
        return JSONResponse(
            status_code=400,
            content={"error": "invalid_doctype", "error_description": f"Unknown doctype: {doctype}"},
        )
