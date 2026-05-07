# DigiLocker Mock — Feature Coverage

This document tracks which DigiLocker Authorized Partner API (v1.11) routes are implemented in this mock and which are intentionally out of scope.

---

## Implemented Routes

These are the only API calls made by the EV charging platform's `digilocker.py` service. The mock implements them faithfully — same endpoint paths, parameter names, response shapes, and error codes as the official spec.

| API | Method | Path | Notes |
|---|---|---|---|
| Get Authorization Code | `GET` | `/public/oauth2/1/authorize` | Serves the consent UI. Validates `client_id`, `response_type`, and `redirect_uri`. Enforces PKCE (`S256`) when `ENFORCE_PKCE=true`. |
| Authorization Callback *(internal)* | `POST` | `/public/oauth2/1/authorize/callback` | Mock-internal route: handles the consent form submit, generates the auth code, and redirects to `redirect_uri`. |
| Get Access Token | `POST` | `/public/oauth2/1/token` | `grant_type=authorization_code`. Validates code, expiry, PKCE verifier, and `redirect_uri` match. |
| Refresh Access Token | `POST` | `/public/oauth2/1/token` | `grant_type=refresh_token`. Rotates both tokens on use. |
| Revoke Token | `POST` | `/public/oauth2/1/revoke` | Removes the token from in-memory state. Always returns `200` (matches real spec). |
| Get User Details | `GET` | `/public/oauth2/1/user` | Returns `digilockerid`, `name`, `dob`, `gender`, `eaadhaar`, `reference_key`. |
| Get List of Issued Documents | `GET` | `/public/oauth2/2/files/issued` | Returns one DL entry plus one entry per vehicle RC. URIs point to the mock's own XML endpoint. |
| Get Certificate Data (XML) | `GET` | `/public/oauth2/3/xml/files` | Accepts `?uri=` query parameter. Parses the mock URI scheme (`https://mock-digilocker/xml/{DL\|RC}/{id}`) and renders the appropriate Jinja2 XML template. Validates that the document belongs to the authenticated persona. |
| Pull Document URI | `POST` | `/public/oauth2/1/pulldocument` | Accepts `doctype=DRVLC` or `doctype=VEHRC` with `parameters[regNo]`. Requires `consent=Y`. Returns a URI pointing to the mock XML endpoint. |

---

## Mock-Only Control Routes

These routes have no equivalent in the real DigiLocker API. They are prefixed `/mock/` to make this obvious. They exist only to support automated testing and local development workflows.

| API | Method | Path | Purpose |
|---|---|---|---|
| Health Check | `GET` | `/mock/health` | Returns `{"status":"ok"}`. Used by Docker/Podman Compose health checks and CI wait loops. |
| List Personas | `GET` | `/mock/personas` | Returns `[{id, label}]` for all loaded personas. Lets test scripts enumerate available test cases without reading `personas.json` directly. |
| Direct Token Issue | `POST` | `/mock/token/direct` | Issues a token pair for a `persona_id` without going through the OAuth consent UI. Used by automated tests that cannot drive a browser. |
| Reset State | `POST` | `/mock/reset` | Clears all in-memory auth codes and tokens. Call in test `teardown` for a clean slate between cases. |

---

## Routes Not Implemented

These DigiLocker APIs are not called by the EV platform and are therefore out of scope for this mock.

| API | Method | Path | Reason skipped |
|---|---|---|---|
| Get List of Self-Uploaded Documents | `GET` | `/public/oauth2/2/files/uploaded` | The platform only needs issued (government-issued) documents, not user-uploaded files. |
| Upload File to Locker | `POST` | `/public/oauth2/2/files/upload` | The platform never writes documents to a user's locker. |
| Get e-Aadhaar Data in XML Format | `GET` | `/public/oauth2/3/xml/eaadhaar` | The platform does not fetch Aadhaar data. |
| DigiLocker Sign Up — Aadhaar OTP | `POST` | `/public/oauth2/1/signup/aadhaarotp` | Sign-up flows are not part of the EV onboarding integration. |
| DigiLocker Sign Up — Verify OTP | `POST` | `/public/oauth2/1/signup/verifyotp` | Same as above. |
| Get Device Code | `GET` | `/public/oauth2/1/device` | The EV platform uses browser-based OAuth, not the device authorization flow. |
| Get Device Access Token | `POST` | `/public/oauth2/1/device/token` | Same as above. |
| Get List of Issuers | `GET` | `/public/oauth2/2/issuers` | The issuer is always MoRTH (`MOTRH`) — hardcoded in the integration. |
| Get List of Documents by Issuer | `GET` | `/public/oauth2/2/issuers/{orgId}/docs` | Document types (`DRVLC`, `VEHRC`) are known and hardcoded. |
| Get Search Parameters | `GET` | `/public/oauth2/2/issuers/{orgId}/docs/{doctype}/searchparams` | Search parameters are known and hardcoded in the EV backend. |
| Verify Account | `GET` | `/public/oauth2/1/verify` | Not used in the EV onboarding flow. |
| Push URI to Account | `POST` | `/public/oauth2/1/pushuri` | The platform never pushes documents into a user's locker. |
| Get Statistics | `GET` | `/public/oauth2/2/statistics` | Internal DigiLocker metric — not relevant to the EV integration. |
