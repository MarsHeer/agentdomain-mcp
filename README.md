# AgentDomain MCP Server

MCP server for [AgentDomain](https://agentdomain.cloud) — register, buy, and manage internet domains as an AI agent.

## Features

- 🔍 Search and check domain availability
- 🛒 Buy domains with automatic Cloudflare registration
- 🌐 Manage DNS records (A, CNAME, MX, TXT, etc.)
- 💰 Wallet balance and top-up
- 🔑 API key auto-saved locally

## Installation

```bash
uvx agentdomain-mcp
```

Or with pip:

```bash
pip install agentdomain-mcp
```

## Configuration

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "agentdomain": {
      "command": "uvx",
      "args": ["agentdomain-mcp"]
    }
  }
}
```

### Cursor / Windsurf

Add to your MCP settings:

```json
{
  "mcpServers": {
    "agentdomain": {
      "command": "uvx",
      "args": ["agentdomain-mcp"]
    }
  }
}
```

### Hermes Agent

Add to `~/.hermes/config.yaml`:

```yaml
mcp_servers:
  agentdomain:
    command: "uvx"
    args: ["agentdomain-mcp"]
```

## Usage

1. **Register** — Call the `register` tool with your name, email, and password
2. **Verify email** — Check your inbox and click the verification link
3. **Top up** — Add funds to your wallet via `wallet_topup`
4. **Search** — Find available domains with `domain_search`
5. **Buy** — Register a domain with `domain_buy`
6. **Manage** — Update DNS records with `domain_dns_update`

## Available Tools

| Tool | Description |
|------|-------------|
| `register` | Create account + save API key |
| `login` | Login to existing account |
| `account_info` | Get account details |
| `domain_search` | Search available domains |
| `domain_check` | Check availability + price |
| `domain_buy` | Register a domain |
| `domain_list` | List your domains |
| `domain_dns_get` | Get DNS records |
| `domain_dns_update` | Update DNS records |
| `domain_transfer` | Get EPP auth code |
| `wallet_balance` | Check balance |
| `wallet_topup` | Create top-up session |
| `wallet_transactions` | List transactions |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AGENTDOMAIN_API` | `https://api.agentdomain.cloud` | API base URL |

## License

MIT
