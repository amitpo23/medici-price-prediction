# Security Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix all CRITICAL and HIGH security vulnerabilities found in the April 2 audit.

**Architecture:** Remove all hardcoded credentials (replace with env vars that fail loudly), add authentication to all unprotected endpoints, fix SQL injection, remove credential leaks from API responses, add security headers.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy, os.getenv()

**Pre-security tag:** `v3.0.1-pre-security` — rollback point

---

### Task 1: Remove Hardcoded Zenith SOAP Credentials

**Files:**
- Modify: `src/utils/zenith_push.py:17-18`
- Modify: `skills/price-override/override_push.py:61-63`

- [ ] **Step 1: Fix zenith_push.py — fail loudly if no env var**

```python
# Lines 17-18: replace defaults with None + runtime check
ZENITH_USERNAME = os.getenv("ZENITH_SOAP_USERNAME")
ZENITH_PASSWORD = os.getenv("ZENITH_SOAP_PASSWORD")

def _require_zenith_creds() -> tuple[str, str]:
    if not ZENITH_USERNAME or not ZENITH_PASSWORD:
        raise RuntimeError("ZENITH_SOAP_USERNAME and ZENITH_SOAP_PASSWORD env vars required")
    return ZENITH_USERNAME, ZENITH_PASSWORD
```

Update `build_soap_envelope` to call `_require_zenith_creds()`.

- [ ] **Step 2: Fix skills/price-override/override_push.py — use env vars**

```python
# Lines 61-63: replace hardcoded with env vars
ZENITH_URL = os.getenv("ZENITH_SOAP_URL", "https://hotel.tools/service/Medici%20new")
ZENITH_USERNAME = os.getenv("ZENITH_SOAP_USERNAME")
ZENITH_PASSWORD = os.getenv("ZENITH_SOAP_PASSWORD")
```

- [ ] **Step 3: Compile check**

Run: `python3 -m py_compile src/utils/zenith_push.py && python3 -m py_compile skills/price-override/override_push.py`

- [ ] **Step 4: Commit**

```bash
git add src/utils/zenith_push.py skills/price-override/override_push.py
git commit -m "security: remove hardcoded Zenith SOAP credentials — require env vars"
```

---

### Task 2: Add Authentication to Unprotected Endpoints in main.py

**Files:**
- Modify: `src/api/main.py` — lines 212, 375, 608, 625, 662

- [ ] **Step 1: Add auth import and dependency**

Add at top of main.py (near existing imports):
```python
from src.api.routers._shared_state import _optional_api_key
```

- [ ] **Step 2: Add auth to /diag endpoints**

```python
@app.get("/diag/price-drop-signals")
def diag_price_drop_signals(_key: str = Depends(_optional_api_key)):

@app.get("/diag/salesoffice-orders")
def diag_salesoffice_orders(_key: str = Depends(_optional_api_key)):
```

- [ ] **Step 3: Add auth to /predict and /train endpoints**

```python
@app.post("/predict", response_model=PredictionResponse)
def predict(request: PredictionRequest, _key: str = Depends(_optional_api_key)):

@app.post("/predict/hotel")
def predict_hotel(request: HotelPredictionRequest, _key: str = Depends(_optional_api_key)):

@app.post("/train")
def train(request: TrainRequest, _key: str = Depends(_optional_api_key)):
```

Apply same pattern to ALL other unprotected endpoints: `/train/multi-source`, `/train/deep-models`, `/train/deep-models/status`, `/train/deep-models/test`, `/train/logs/stats`.

- [ ] **Step 4: Compile check**

Run: `python3 -m py_compile src/api/main.py`

- [ ] **Step 5: Commit**

```bash
git add src/api/main.py
git commit -m "security: add API key auth to /predict, /train, /diag endpoints"
```

---

### Task 3: Add Authentication to AI Endpoints

**Files:**
- Modify: `src/api/routers/ai_router.py` — lines 20, 146, 171, 192, 220

- [ ] **Step 1: Add auth import**

```python
from src.api.routers._shared_state import _optional_api_key
```

- [ ] **Step 2: Add auth dependency to all 5 endpoints**

Add `_key: str = Depends(_optional_api_key)` parameter to each endpoint function.

- [ ] **Step 3: Compile check**

Run: `python3 -m py_compile src/api/routers/ai_router.py`

- [ ] **Step 4: Commit**

```bash
git add src/api/routers/ai_router.py
git commit -m "security: add API key auth to all AI endpoints"
```

---

### Task 4: Remove SOAP Preview Credential Leak

**Files:**
- Modify: `src/api/routers/analytics_router.py:2743-2747`

- [ ] **Step 1: Replace soap_preview with safe message**

```python
zenith_result = {
    "status": "dry_run",
    "detail": "OVERRIDE_PUSH_ENABLED=false — Zenith push skipped. Set to true to enable.",
    "would_push_to": f"hotel={hotel_code}, itc={itc}, rpc={rpc}, date={date_from}, amount=${target_price:.2f}",
}
```

Remove `"soap_preview": soap[:300] + "..."` entirely.

- [ ] **Step 2: Compile check**

Run: `python3 -m py_compile src/api/routers/analytics_router.py`

- [ ] **Step 3: Commit**

```bash
git add src/api/routers/analytics_router.py
git commit -m "security: remove SOAP XML preview that leaked credentials in dry-run response"
```

---

### Task 5: Remove Traceback from API Responses

**Files:**
- Modify: `src/api/routers/analytics_router.py:1098-1099`
- Modify: `src/api/routers/monitor_router.py:104,132,151`

- [ ] **Step 1: Fix debug endpoint — remove traceback**

```python
except (ValueError, TypeError, KeyError, OSError) as e:
    logger.error("Debug collection cycle failed", exc_info=True)
    return {"status": "error", "error": "Collection cycle failed — check server logs"}
```

- [ ] **Step 2: Fix monitor_router — generic error messages**

```python
# Line 104:
raise HTTPException(status_code=500, detail="Monitor query failed — check server logs")

# Line 132:
raise HTTPException(status_code=500, detail="Hotel adjustment query failed — check server logs")

# Line 151:
raise HTTPException(status_code=500, detail="Hotel metrics query failed — check server logs")
```

- [ ] **Step 3: Compile check**

Run: `python3 -m py_compile src/api/routers/analytics_router.py && python3 -m py_compile src/api/routers/monitor_router.py`

- [ ] **Step 4: Commit**

```bash
git add src/api/routers/analytics_router.py src/api/routers/monitor_router.py
git commit -m "security: remove traceback and raw errors from API responses"
```

---

### Task 6: Fix SQL Injection in db_loader.py

**Files:**
- Modify: `src/data/db_loader.py:16-28`

- [ ] **Step 1: Add allowlist validation**

```python
_ALLOWED_TABLES = frozenset({
    "bookings", "rooms", "rates", "hotels",
})

def load_table(table_name: str, columns: str = "*", limit: int | None = None) -> pd.DataFrame:
    if table_name not in _ALLOWED_TABLES:
        raise ValueError(f"Table '{table_name}' not in allowed list")
    if columns != "*":
        cols = [c.strip() for c in columns.split(",")]
        if not all(c.isidentifier() for c in cols):
            raise ValueError(f"Invalid column names: {columns}")
        columns = ", ".join(cols)
    engine = get_engine()
    query = f"SELECT {columns} FROM {table_name}"
    if limit:
        query += f" ORDER BY 1 OFFSET 0 ROWS FETCH NEXT {limit} ROWS ONLY"
    return pd.read_sql(text(query), engine)
```

- [ ] **Step 2: Compile check**

Run: `python3 -m py_compile src/data/db_loader.py`

- [ ] **Step 3: Commit**

```bash
git add src/data/db_loader.py
git commit -m "security: add table/column allowlist to prevent SQL injection in db_loader"
```

---

### Task 7: Fix API Key Prefix Logging

**Files:**
- Modify: `src/api/routers/_shared_state.py:58`

- [ ] **Step 1: Log IP instead of key prefix**

```python
logger.warning("Failed auth attempt from %s on %s", 
    getattr(getattr(request, 'client', None), 'host', 'unknown'), 
    getattr(request, 'url', 'unknown'))
```

Note: `_optional_api_key` doesn't have `request` in scope. Instead, just remove the key prefix:

```python
logger.warning("Failed API key authentication attempt")
```

- [ ] **Step 2: Compile check**

Run: `python3 -m py_compile src/api/routers/_shared_state.py`

- [ ] **Step 3: Commit**

```bash
git add src/api/routers/_shared_state.py
git commit -m "security: stop logging API key prefix on auth failure"
```

---

### Task 8: Add Security Headers Middleware

**Files:**
- Modify: `src/api/middleware.py`

- [ ] **Step 1: Add SecurityHeadersMiddleware class**

```python
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        if os.environ.get("IS_PRODUCTION"):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response
```

- [ ] **Step 2: Wire into setup_middleware()**

Add `app.add_middleware(SecurityHeadersMiddleware)` before SchedulerWatchdog.

- [ ] **Step 3: Compile check**

Run: `python3 -m py_compile src/api/middleware.py`

- [ ] **Step 4: Commit**

```bash
git add src/api/middleware.py
git commit -m "security: add security headers middleware (nosniff, DENY, HSTS)"
```

---

### Task 9: Warn on Missing API Key at Startup

**Files:**
- Modify: `src/api/middleware.py:58-60`

- [ ] **Step 1: Add startup warning**

```python
def verify_api_key(x_api_key: str) -> bool:
    configured = os.environ.get("PREDICTION_API_KEY", "")
    if not configured:
        return True  # No key configured = open access
    valid_keys = {k.strip() for k in configured.split(",") if k.strip()}
    return x_api_key in valid_keys

def warn_if_no_api_key() -> None:
    if not os.environ.get("PREDICTION_API_KEY", ""):
        logger.critical(
            "PREDICTION_API_KEY not set — API is OPEN ACCESS. "
            "Set PREDICTION_API_KEY env var for production."
        )
```

- [ ] **Step 2: Call warn_if_no_api_key() from main.py startup**

Add after `setup_middleware(app)`:
```python
from src.api.middleware import warn_if_no_api_key
warn_if_no_api_key()
```

- [ ] **Step 3: Compile check**

Run: `python3 -m py_compile src/api/middleware.py && python3 -m py_compile src/api/main.py`

- [ ] **Step 4: Commit**

```bash
git add src/api/middleware.py src/api/main.py
git commit -m "security: CRITICAL log warning when PREDICTION_API_KEY not configured"
```

---

### Task 10: Update .gitignore

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add missing exclusions**

```
# Security — credential-bearing files
skills/*/config.json
scripts/tmp_*
.playwright-mcp/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore
git commit -m "security: exclude credential-bearing temp files from git tracking"
```

---

### Task 11: Final Verification

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest tests/ -x -q --timeout=30`

- [ ] **Step 2: Compile all modified files**

Run: `python3 -m py_compile src/api/main.py src/api/middleware.py src/utils/zenith_push.py src/data/db_loader.py src/api/routers/analytics_router.py src/api/routers/ai_router.py src/api/routers/monitor_router.py src/api/routers/_shared_state.py`

- [ ] **Step 3: Tag release**

```bash
git tag -a v3.0.1-security -m "Security hardening — credentials, auth, headers, SQL injection"
```
