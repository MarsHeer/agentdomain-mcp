"""AgentDomain MCP Server — Register, buy, and manage domains as an AI agent."""

import os
import re
import json
import stat
import logging
import httpx
from typing import Any
from mcp.server.fastmcp import FastMCP

# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agentdomain-mcp")

API_BASE = os.environ.get("AGENTDOMAIN_API", "https://api.agentdomain.cloud")
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".agentdomain")
CREDENTIALS_FILE = os.path.join(CONFIG_DIR, "credentials.json")

# Domain name regex: labels separated by dots, alphanumeric + hyphens, 1-63 chars each
_DOMAIN_RE = re.compile(r"^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63}(?<!-))*\.[A-Za-z]{2,}$")
_EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")

mcp = FastMCP(
    "AgentDomain",
    instructions=(
        "Register and manage internet domains for AI agents. "
        "First call register or login to authenticate, then use domain tools."
    ),
)


# ── Credential management (chmod 600, merge-safe) ────────────────────────

def _load_credentials() -> dict:
    """Load saved credentials with restricted file permissions."""
    if not os.path.exists(CREDENTIALS_FILE):
        return {}
    try:
        # Verify file permissions are restrictive
        st = os.stat(CREDENTIALS_FILE)
        mode = st.st_mode
        if mode & (stat.S_IRGRP | stat.S_IROTH | stat.S_IWGRP | stat.S_IWOTH):
            logger.warning("Credentials file has loose permissions; fixing to 0o600")
            os.chmod(CREDENTIALS_FILE, stat.S_IRUSR | stat.S_IWUSR)

        with open(CREDENTIALS_FILE) as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.error("Credentials file is corrupted; starting fresh")
        return {}
    except OSError as e:
        logger.error("Failed to read credentials: %s", e)
        return {}


def _save_credentials(new_data: dict):
    """Save credentials to disk with restricted permissions. Merges with existing data."""
    os.makedirs(CONFIG_DIR, mode=0o700, exist_ok=True)
    existing = _load_credentials()

    # Merge: new data overwrites existing keys, but log conflicts
    for key, value in new_data.items():
        if key in existing and existing[key] != value:
            logger.warning("Credential key '%s' is being overwritten", key)
        existing[key] = value

    try:
        tmp_path = CREDENTIALS_FILE + ".tmp"
        with open(tmp_path, "w") as f:
            json.dump(existing, f, indent=2)
        os.replace(tmp_path, CREDENTIALS_FILE)
        os.chmod(CREDENTIALS_FILE, stat.S_IRUSR | stat.S_IWUSR)
        logger.info("Credentials saved successfully")
    except OSError as e:
        logger.error("Failed to save credentials: %s", e)
        raise


def _headers() -> dict:
    creds = _load_credentials()
    api_key = creds.get("api_key", "")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _mask_key(key: str) -> str:
    """Mask an API key for safe display in logs/errors."""
    if not key or len(key) < 12:
        return "***"
    return f"{key[:4]}...{key[-4:]}"


# ── Input validation ──────────────────────────────────────────────────────

def _validate_domain(domain: str) -> str:
    """Validate and sanitize a domain name. Returns the cleaned domain or raises ValueError."""
    domain = domain.strip().lower()
    if not _DOMAIN_RE.match(domain):
        raise ValueError(
            f"Invalid domain name: '{domain}'. Must be a valid domain like 'example.com'."
        )
    return domain


def _validate_email(email: str) -> str:
    """Validate email format."""
    email = email.strip()
    if not _EMAIL_RE.match(email):
        raise ValueError(f"Invalid email format: '{email}'")
    return email


def _validate_password(password: str) -> str:
    """Validate password meets minimum requirements."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    return password


# ── HTTP helpers (specific exceptions, timeouts, retries) ─────────────────

async def _request(
    method: str,
    path: str,
    data: dict = None,
    params: dict = None,
    retries: int = 2,
) -> dict:
    """Make an HTTP request with specific error handling and retries."""
    url = f"{API_BASE}{path}"
    last_error = None

    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(15.0, connect=10.0)) as client:
                if method == "GET":
                    r = await client.get(url, headers=_headers(), params=params)
                elif method == "POST":
                    r = await client.post(url, headers=_headers(), json=data or {})
                elif method == "PUT":
                    r = await client.put(url, headers=_headers(), json=data or {})
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                r.raise_for_status()
                return r.json()

        except httpx.TimeoutException as e:
            last_error = e
            logger.warning("Request to %s timed out (attempt %d/%d)", path, attempt + 1, retries + 1)
            continue
        except httpx.HTTPStatusError as e:
            # Sanitize: never expose API key in error messages
            status = e.response.status_code
            try:
                body = e.response.json()
                detail = body.get("error", body.get("message", f"HTTP {status}"))
            except Exception:
                detail = f"HTTP {status}"
            logger.error("API error on %s: %s", path, detail)
            raise RuntimeError(f"API error ({status}): {detail}") from e
        except httpx.ConnectError as e:
            last_error = e
            logger.warning("Connection error to %s (attempt %d)", path, attempt + 1)
            continue
        except Exception as e:
            # Never log the full exception if it might contain credentials
            logger.error("Unexpected error on %s: %s", path, type(e).__name__)
            raise RuntimeError(f"Request failed: {type(e).__name__}") from e

    raise RuntimeError(f"Request to {path} failed after {retries + 1} attempts: {last_error}")


async def _get(path: str, params: dict = None) -> dict:
    return await _request("GET", path, params=params)


async def _post(path: str, data: dict = None) -> dict:
    return await _request("POST", path, data=data)


async def _put(path: str, data: dict = None) -> dict:
    return await _request("PUT", path, data=data)


# ── Auth ──────────────────────────────────────────────────────────────────

@mcp.tool()
async def register(
    name: str,
    email: str,
    password: str,
    billing_name: str = "",
    billing_address: str = "",
    billing_city: str = "",
    billing_country: str = "US",
    billing_postal: str = "",
) -> str:
    """Create a new AgentDomain account and save the API key.

    Call this first if you don't have an account. The API key is saved
    automatically for future calls.
    """
    email = _validate_email(email)
    _validate_password(password)

    billing = {}
    if billing_name:
        billing["name"] = billing_name
    if billing_address:
        billing["address1"] = billing_address
    if billing_city:
        billing["city"] = billing_city
    if billing_country:
        billing["country"] = billing_country
    if billing_postal:
        billing["postal_code"] = billing_postal

    payload = {"name": name, "email": email, "password": password}
    if billing:
        payload["billing"] = billing

    logger.info("Registering new account for %s", _mask_key(email))
    result = await _post("/v1/auth/register", payload)

    if "api_key" in result:
        _save_credentials({"api_key": result["api_key"], "email": email, "name": name})
        logger.info("Account created and API key saved for %s", _mask_key(email))
        return "✅ Account created! API key saved securely. Email verification required before buying domains."
    return f"Registration response: {json.dumps(result)}"


@mcp.tool()
async def login(email: str, password: str) -> str:
    """Login to an existing AgentDomain account and save the API key."""
    email = _validate_email(email)
    _validate_password(password)

    logger.info("Login attempt for %s", _mask_key(email))
    result = await _post("/v1/auth/login", {"email": email, "password": password})
    if "api_key" in result:
        _save_credentials({"api_key": result["api_key"], "email": email})
        logger.info("Login successful for %s", _mask_key(email))
        return "✅ Logged in! API key saved securely."
    return f"Login response: {json.dumps(result)}"


@mcp.tool()
async def account_info() -> str:
    """Get current account details (name, email, verification status)."""
    result = await _get("/v1/auth/me")
    return json.dumps(result, indent=2)


# ── Domains ───────────────────────────────────────────────────────────────

@mcp.tool()
async def domain_search(query: str, limit: int = 10) -> str:
    """Search for available domains matching a keyword.

    Returns a list of available domain names with prices.
    """
    query = query.strip()
    if not query or len(query) > 100:
        raise ValueError("Search query must be 1-100 characters")
    limit = max(1, min(limit, 50))
    result = await _get("/v1/domains/search", {"q": query, "limit": limit})
    return json.dumps(result, indent=2)


@mcp.tool()
async def domain_check(domain: str) -> str:
    """Check if a specific domain is available and get its price.

    Returns availability status and registration cost.
    """
    domain = _validate_domain(domain)
    result = await _post("/v1/domains/check", {"domain": domain})
    return json.dumps(result, indent=2)


@mcp.tool()
async def domain_buy(domain: str, years: int = 1) -> str:
    """Register/buy a domain.

    Requires sufficient wallet balance. The domain will be registered
    through Cloudflare and DNS records can be managed immediately.
    """
    domain = _validate_domain(domain)
    years = max(1, min(years, 10))
    result = await _post("/v1/domains/buy", {"domain": domain, "years": years})
    return json.dumps(result, indent=2)


@mcp.tool()
async def domain_list() -> str:
    """List all domains registered on your account.

    Returns domain names, status, expiration dates, and nameservers.
    """
    result = await _get("/v1/domains")
    return json.dumps(result, indent=2)


@mcp.tool()
async def domain_dns_get(domain: str) -> str:
    """Get DNS records for a domain.

    Returns all DNS records (A, CNAME, MX, TXT, etc.) for the domain.
    """
    domain = _validate_domain(domain)
    result = await _get(f"/v1/domains/{domain}/dns")
    return json.dumps(result, indent=2)


@mcp.tool()
async def domain_dns_update(
    domain: str,
    records: list[dict[str, Any]],
) -> str:
    """Update DNS records for a domain.

    Each record should have: type, name, content, ttl, and optionally proxied.
    Example: {"type": "A", "name": "@", "content": "1.2.3.4", "ttl": 300, "proxied": false}
    """
    domain = _validate_domain(domain)

    # Validate record types
    valid_types = {"A", "AAAA", "CNAME", "MX", "TXT", "SRV", "NS", "CAA", "PTR"}
    for i, rec in enumerate(records):
        rec_type = rec.get("type", "").upper()
        if rec_type not in valid_types:
            raise ValueError(f"Record {i}: invalid type '{rec_type}'. Must be one of: {valid_types}")
        if not rec.get("name"):
            raise ValueError(f"Record {i}: 'name' is required")
        if not rec.get("content"):
            raise ValueError(f"Record {i}: 'content' is required")

    result = await _put(f"/v1/domains/{domain}/dns", {"records": records})
    return json.dumps(result, indent=2)


@mcp.tool()
async def domain_transfer(domain: str) -> str:
    """Get the EPP authorization code to transfer a domain to another registrar.

    Returns the auth code needed for domain transfer.
    """
    domain = _validate_domain(domain)
    result = await _post(f"/v1/domains/{domain}/transfer")
    return json.dumps(result, indent=2)


# ── Wallet ────────────────────────────────────────────────────────────────

@mcp.tool()
async def wallet_balance() -> str:
    """Check your AgentDomain wallet balance.

    Returns balance in cents and spending limits.
    """
    result = await _get("/v1/wallet")
    return json.dumps(result, indent=2)


@mcp.tool()
async def wallet_topup(amount_cents: int) -> str:
    """Create a card top-up session for your wallet.

    Returns a Stripe Checkout URL to complete payment.
    """
    if amount_cents < 100 or amount_cents > 100000:
        raise ValueError("Top-up amount must be between $1.00 and $1,000.00 (100-100000 cents)")
    result = await _post("/v1/wallet/topup/card", {"amount_cents": amount_cents})
    return json.dumps(result, indent=2)


@mcp.tool()
async def wallet_transactions(limit: int = 20) -> str:
    """List recent wallet transactions.

    Shows domain purchases, top-ups, and refunds.
    """
    limit = max(1, min(limit, 100))
    result = await _get("/v1/wallet/transactions", {"limit": limit})
    return json.dumps(result, indent=2)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
