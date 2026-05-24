"""AgentDomain MCP Server — Register, buy, and manage domains as an AI agent."""

import os
import json
import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = os.environ.get("AGENTDOMAIN_API", "https://api.agentdomain.cloud")
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".agentdomain")
CREDENTIALS_FILE = os.path.join(CONFIG_DIR, "credentials.json")

mcp = FastMCP(
    "AgentDomain",
    instructions=(
        "Register and manage internet domains for AI agents. "
        "First call register or login to authenticate, then use domain tools."
    ),
)


def _load_credentials() -> dict:
    """Load saved credentials."""
    if os.path.exists(CREDENTIALS_FILE):
        with open(CREDENTIALS_FILE) as f:
            return json.load(f)
    return {}


def _save_credentials(data: dict):
    """Save credentials to disk."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    existing = _load_credentials()
    existing.update(data)
    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(existing, f, indent=2)


def _headers() -> dict:
    creds = _load_credentials()
    api_key = creds.get("api_key", "")
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


async def _get(path: str, params: dict = None) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_BASE}{path}", headers=_headers(), params=params, timeout=30)
        r.raise_for_status()
        return r.json()


async def _post(path: str, data: dict = None) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{API_BASE}{path}", headers=_headers(), json=data or {}, timeout=30)
        r.raise_for_status()
        return r.json()


async def _put(path: str, data: dict = None) -> dict:
    async with httpx.AsyncClient() as c:
        r = await c.put(f"{API_BASE}{path}", headers=_headers(), json=data or {}, timeout=30)
        r.raise_for_status()
        return r.json()


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

    result = await _post("/v1/auth/register", payload)

    if "api_key" in result:
        _save_credentials({"api_key": result["api_key"], "email": email, "name": name})
        return f"✅ Account created! API key saved to {CREDENTIALS_FILE}. Email verification required before buying domains."
    return f"Registration response: {json.dumps(result)}"


@mcp.tool()
async def login(email: str, password: str) -> str:
    """Login to an existing AgentDomain account and save the API key."""
    result = await _post("/v1/auth/login", {"email": email, "password": password})
    if "api_key" in result:
        _save_credentials({"api_key": result["api_key"], "email": email})
        return f"✅ Logged in! API key saved."
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
    result = await _get("/v1/domains/search", {"q": query, "limit": limit})
    return json.dumps(result, indent=2)


@mcp.tool()
async def domain_check(domain: str) -> str:
    """Check if a specific domain is available and get its price.

    Returns availability status and registration cost.
    """
    result = await _post("/v1/domains/check", {"domain": domain})
    return json.dumps(result, indent=2)


@mcp.tool()
async def domain_buy(domain: str, years: int = 1) -> str:
    """Register/buy a domain.

    Requires sufficient wallet balance. The domain will be registered
    through Cloudflare and DNS records can be managed immediately.
    """
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
    result = await _get(f"/v1/domains/{domain}/dns")
    return json.dumps(result, indent=2)


@mcp.tool()
async def domain_dns_update(
    domain: str,
    records: list[dict],
) -> str:
    """Update DNS records for a domain.

    Each record should have: type, name, content, ttl, and optionally proxied.
    Example: {"type": "A", "name": "@", "content": "1.2.3.4", "ttl": 300, "proxied": false}
    """
    result = await _put(f"/v1/domains/{domain}/dns", {"records": records})
    return json.dumps(result, indent=2)


@mcp.tool()
async def domain_transfer(domain: str) -> str:
    """Get the EPP authorization code to transfer a domain to another registrar.

    Returns the auth code needed for domain transfer.
    """
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
    result = await _post("/v1/wallet/topup/card", {"amount_cents": amount_cents})
    return json.dumps(result, indent=2)


@mcp.tool()
async def wallet_transactions(limit: int = 20) -> str:
    """List recent wallet transactions.

    Shows domain purchases, top-ups, and refunds.
    """
    result = await _get("/v1/wallet/transactions", {"limit": limit})
    return json.dumps(result, indent=2)


# ── Free Subdomains (agentfolio.dev) ──────────────────────────────────────

@mcp.tool()
async def claim_subdomain(name: str) -> str:
    """Claim a free subdomain on agentfolio.dev (e.g., 'my-agent' → my-agent.agentfolio.dev).

    No payment required. The subdomain is yours forever.
    Use it as a home page for your agent or point it to your server.
    """
    result = await _post("/v1/subdomains/claim", {"subdomain": name})
    return json.dumps(result, indent=2)


@mcp.tool()
async def check_subdomain(name: str) -> str:
    """Check if a subdomain on agentfolio.dev is available.

    Returns whether the name is free to claim.
    """
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_BASE}/v1/subdomains/check/{name}", timeout=30)
        r.raise_for_status()
        return json.dumps(r.json(), indent=2)


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
