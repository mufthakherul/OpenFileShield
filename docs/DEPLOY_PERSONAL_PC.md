# Public Deployment From Personal PC

This guide lets your locally running service become globally accessible.

## Option 1: Cloudflare Tunnel (Recommended)

1. Keep app running on `localhost:8080`.
2. Install `cloudflared`.
3. Authenticate Cloudflare and create tunnel.
4. Route tunnel hostname to local app.
5. Enable HTTPS and bot protections in Cloudflare dashboard.

Example:

```bash
cloudflared tunnel login
cloudflared tunnel create openfileshield
cloudflared tunnel route dns openfileshield your-upload-domain.example.com
cloudflared tunnel run openfileshield
```

Use tunnel config to map service to `http://localhost:8080`.

## Option 2: Port Forwarding + Reverse Proxy

1. Reserve local static IP for your PC.
2. Forward port 443 from router to reverse proxy host.
3. Run Caddy or Nginx with TLS certificates.
4. Proxy traffic to app on `localhost:8080`.

## Option 3: Ngrok (Quick Start)

```bash
ngrok http 8080
```

## Minimum Production Controls

- HTTPS only
- WAF or DDoS protection
- upload rate limiting
- routine backups
- malware signature updates
- legal consent and privacy notice
