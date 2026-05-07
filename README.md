
# DigiLocker Mock Server

A standalone FastAPI application that faithfully mimics the [DigiLocker Authorized Partner API (v1.11)](https://partners.digitallocker.gov.in/assets/img/Digital%20Locker%20Authorized%20Partner%20API%20Specification.pdf) for local development and CI environments.

Any application that points `DIGILOCKER_BASE_URL` at this mock instead of `https://api.digitallocker.gov.in` will behave identically — **no code changes needed to switch between environments**.

## Contents

* [Quick Start](#quick-start)

  * [Running directly with Python](#running-directly-with-python)
  * [Running with Docker](#running-with-docker)
  * [Running with Podman](#running-with-podman)
  * [Running as part of Docker Compose](#running-as-part-of-docker-compose)
* [Configuration](#configuration)
* [Test Personas](#test-personas)
* [Using in Automated Tests](#using-in-automated-tests)

## Quick Start

### Running directly with Python

Requires Python 3.12+.

```bash
cd dev-tools/digilocker-mock

# Install dependencies
pip install -r requirements.txt

# Start the server
uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```

The server will be available at `http://localhost:8001`.

### Running with Docker

```bash
cd dev-tools/digilocker-mock

# Build the image
docker build -t digilocker-mock .

# Run the container
docker run --rm -p 8001:8001 digilocker-mock
```

Override configuration at runtime with environment variables:

```bash
docker run --rm -p 8001:8001 \
  -e CLIENT_ID=my_client_id \
  -e CLIENT_SECRET=my_client_secret \
  -e ENFORCE_PKCE=false \
  digilocker-mock
```

### Running with Podman

The image is fully compatible with Podman — no changes needed.

```bash
cd dev-tools/digilocker-mock

# Build the image
podman build -t digilocker-mock .

# Run the container
podman run --rm -p 8001:8001 digilocker-mock
```

Override configuration:

```bash
podman run --rm -p 8001:8001 \
  -e CLIENT_ID=my_client_id \
  -e CLIENT_SECRET=my_client_secret \
  -e ENFORCE_PKCE=false \
  digilocker-mock
```

To run as a detached background service with Podman:

```bash
podman run -d --name digilocker-mock -p 8001:8001 digilocker-mock

# Check it is healthy
curl http://localhost:8001/mock/health

# Stop it
podman stop digilocker-mock
```

### Running as part of Docker Compose

Add the following service to your `docker-compose.yml`:

```yaml
services:
  digilocker-mock:
    build: ./dev-tools/digilocker-mock
    ports:
      - "8001:8001"
    environment:
      CLIENT_ID: mock_client_id
      CLIENT_SECRET: mock_client_secret
      ENFORCE_PKCE: "true"
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8001/mock/health"]
      interval: 5s
      timeout: 3s
      retries: 5
```

Then configure your application's `.env` for development:

```dotenv
DIGILOCKER_BASE_URL=http://digilocker-mock:8001
DIGILOCKER_CLIENT_ID=mock_client_id
DIGILOCKER_CLIENT_SECRET=mock_client_secret
DIGILOCKER_REDIRECT_URI=http://localhost:8000/v1/onboarding/digilocker/callback
```

In staging/production, set `DIGILOCKER_BASE_URL=https://api.digitallocker.gov.in`. No other code changes are required.

## Configuration

All configuration is through environment variables (or a `.env` file in the same directory).

| Variable                   | Default              | Description                                                                                                       |
| -------------------------- | -------------------- | ----------------------------------------------------------------------------------------------------------------- |
| `PORT`                     | `8001`               | Port the server listens on                                                                                        |
| `HOST`                     | `0.0.0.0`            | Host/interface to bind                                                                                            |
| `CLIENT_ID`                | `mock_client_id`     | OAuth client ID — must match what the backend sends                                                               |
| `CLIENT_SECRET`            | `mock_client_secret` | OAuth client secret — must match what the backend sends                                                           |
| `ENFORCE_PKCE`             | `true`               | When `true`, requires `code_challenge`/`code_verifier` in the OAuth flow. Set to `false` for quick manual testing |
| `ACCESS_TOKEN_EXPIRES_IN`  | `3600`               | Access token lifetime in seconds                                                                                  |
| `REFRESH_TOKEN_EXPIRES_IN` | `86400`              | Refresh token lifetime in seconds                                                                                 |
| `PERSONAS_FILE`            | `personas.json`      | Path to the personas file (absolute or relative to the app directory)                                             |

Example `.env` file for local development with PKCE disabled:

```dotenv
CLIENT_ID=mock_client_id
CLIENT_SECRET=mock_client_secret
ENFORCE_PKCE=false
```

## Test Personas

Personas are defined in `personas.json`. Each persona is a complete test identity with a driving licence and zero or more vehicle registrations.

| Persona ID          | Label                       | DL Status   | Vehicles                      |
| ------------------- | --------------------------- | ----------- | ----------------------------- |
| `driver_full`       | Driver — DL + 2 vehicle RCs | Valid       | 2 (Tata Nexon EV, Ather 450X) |
| `driver_no_rc`      | Driver — DL only, no RCs    | Valid       | 0                             |
| `driver_dl_expired` | Driver — DL expired         | **Expired** | 1 (MG ZS EV)                  |
| `host_only`         | Host — DL only, no vehicles | Valid       | 0                             |

### Adding a new persona

Edit `personas.json` and add an entry following the existing schema. No code change is needed — the server picks up new personas on restart.

```json
{
  "id": "my_test_case",
  "label": "My descriptive label",
  "digilockerid": "eeeeeeee-0005-0005-0005-eeeeeeeeeeee",
  "name": "Test User",
  "dob": "01011990",
  "gender": "M",
  "eaadhaar": "Y",
  "reference_key": "mock_ref_005",
  "driving_license": {
    "dl_number": "DL0120250099999",
    "issue_date": "2025-01-01",
    "expiry_date": "2045-01-01",
    "issuing_authority": "DTO Delhi",
    "state": "Delhi",
    "vehicle_classes": ["LMV"],
    "status": "valid"
  },
  "vehicles": []
}
```

## Using in Automated Tests

The typical pattern for an automated integration test:

```python
import httpx

BASE = "http://localhost:8001"

def setup():
    # Reset state before each test
    httpx.post(f"{BASE}/mock/reset")

def test_user_details():
    # Get a token directly — no browser needed
    resp = httpx.post(f"{BASE}/mock/token/direct", json={"persona_id": "driver_full"})
    token = resp.json()["access_token"]

    # Call the real DigiLocker-spec endpoint
    user = httpx.get(
        f"{BASE}/public/oauth2/1/user",
        headers={"Authorization": f"Bearer {token}"},
    ).json()

    assert user["name"] == "Harpreet Singh"
```
