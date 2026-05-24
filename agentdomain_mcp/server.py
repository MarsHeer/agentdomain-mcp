#!/usr/bin/env python3
"""AgentDomain MCP Server — Streamable HTTP on port 8801."""

import os
import json
import logging
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("agentdomain-mcp")

API_BASE = os.environ.get("AGENTDOMAIN_API", "https://api.agentdomain.cloud")

mcp = FastMCP(
    "AgentDomain",
    instructions="Register and manage internet domains for AI agents via AgentDomain.",
    host="0.0.0.0",
    port=8801,
    json_response=True,
    streamable_http_path="/mcp",
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=False,
    ),
)


async def _get(path, token, params=None):
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_BASE}{path}", headers=h, params=params, timeout=30)
        r.raise_for_status()
        return r.json()

async def _post(path, token, data=None):
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient() as c:
        r = await c.post(f"{API_BASE}{path}", headers=h, json=data or {}, timeout=30)
        r.raise_for_status()
        return r.json()

async def _put(path, token, data=None):
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    async with httpx.AsyncClient() as c:
        r = await c.put(f"{API_BASE}{path}", headers=h, json=data or {}, timeout=30)
        r.raise_for_status()
        return r.json()


@mcp.tool()
async def register(name: str, email: str, password: str, billing_name: str = "", billing_address: str = "", billing_city: str = "", billing_country: str = "US", billing_postal: str = "") -> str:
    """Create a new AgentDomain account."""
    billing = {}
    if billing_name: billing["name"] = billing_name
    if billing_address: billing["address1"] = billing_address
    if billing_city: billing["city"] = billing_city
    if billing_country: billing["country"] = billing_country
    if billing_postal: billing["postal_code"] = billing_postal
    payload = {"name": name, "email": email, "password": password}
    if billing: payload["billing"] = billing
    result = await _post("/v1/auth/register", "", payload)
    if "api_key" in result:
        return json.dumps({"status": "ok", "api_key": result["api_key"]})
    return json.dumps(result)

@mcp.tool()
async def login(email: str, password: str) -> str:
    """Login and get API key."""
    result = await _post("/v1/auth/login", "", {"email": email, "password": password})
    if "api_key" in result:
        return json.dumps({"status": "ok", "api_key": result["api_key"]})
    return json.dumps(result)

@mcp.tool()
async def account_info(api_key: str) -> str:
    """Get account details."""
    return json.dumps(await _get("/v1/auth/me", api_key))

@mcp.tool()
async def domain_search(api_key: str, query: str, limit: int = 10) -> str:
    """Search available domains."""
    return json.dumps(await _get("/v1/domains/search", api_key, {"q": query, "limit": limit}))

@mcp.tool()
async def domain_check(api_key: str, domain: str) -> str:
    """Check domain availability and price."""
    return json.dumps(await _post("/v1/domains/check", api_key, {"domain": domain}))

@mcp.tool()
async def domain_buy(api_key: str, domain: str, years: int = 1) -> str:
    """Register a domain."""
    return json.dumps(await _post("/v1/domains/buy", api_key, {"domain": domain, "years": years}))

@mcp.tool()
async def domain_list(api_key: str) -> str:
    """List your domains."""
    return json.dumps(await _get("/v1/domains", api_key))

@mcp.tool()
async def domain_dns_get(api_key: str, domain: str) -> str:
    """Get DNS records."""
    return json.dumps(await _get(f"/v1/domains/{domain}/dns", api_key))

@mcp.tool()
async def domain_dns_update(api_key: str, domain: str, records: list) -> str:
    """Update DNS records."""
    return json.dumps(await _put(f"/v1/domains/{domain}/dns", api_key, {"records": records}))

@mcp.tool()
async def domain_transfer(api_key: str, domain: str) -> str:
    """Get EPP auth code for transfer."""
    return json.dumps(await _post(f"/v1/domains/{domain}/transfer", api_key))

@mcp.tool()
async def wallet_balance(api_key: str) -> str:
    """Check wallet balance."""
    return json.dumps(await _get("/v1/wallet", api_key))

@mcp.tool()
async def wallet_topup(api_key: str, amount_cents: int) -> str:
    """Create top-up session."""
    return json.dumps(await _post("/v1/wallet/topup/card", api_key, {"amount_cents": amount_cents}))

@mcp.tool()
async def wallet_transactions(api_key: str, limit: int = 20) -> str:
    """List recent transactions."""
    return json.dumps(await _get("/v1/wallet/transactions", api_key, {"limit": limit}))


@mcp.tool()
async def claim_subdomain(api_key: str, name: str) -> str:
    """Claim a free subdomain on agentfolio.dev (e.g., 'my-agent' → my-agent.agentfolio.dev).
    
    Requires an authenticated and verified AgentDomain account.
    Each agent gets one free subdomain.
    """
    return json.dumps(await _post("/v1/subdomains/claim", api_key, {"subdomain": name}))


@mcp.tool()
async def check_subdomain(name: str) -> str:
    """Check if a subdomain on agentfolio.dev is available."""
    async with httpx.AsyncClient() as c:
        r = await c.get(f"{API_BASE}/v1/subdomains/check/{name}", timeout=30)
        r.raise_for_status()
        return json.dumps(r.json())


if __name__ == "__main__":
    logger.info("Starting AgentDomain MCP Server on port 8801")
    mcp.run(transport="streamable-http")
