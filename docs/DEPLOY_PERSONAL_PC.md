# Public Deployment From Personal PC

This guide lets your uploader service become globally accessible while keeping admin local/private.

Recommended local ports:

- Public uploader: `8080`
- Admin dashboard: `8081`

## Option 1: Cloudflare Tunnel (Recommended)

1. Keep public app running on `localhost:8080` and admin on `localhost:8081`.
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

Use tunnel config to map uploader service to `http://localhost:8080`.
Do not map admin unless additional private access controls are enforced.

## Option 2: Port Forwarding + Reverse Proxy

1. Reserve local static IP for your PC.
2. Forward port 443 from router to reverse proxy host.
3. Run Caddy or Nginx with TLS certificates.
4. Proxy traffic to app on `localhost:8080`.
5. Keep admin route/domain private and forward only from trusted local/private CIDRs.

## Option 3: Ngrok (Quick Start)

```bash
ngrok http 8080
```

Do not expose `8081` publicly.

## Minimum Production Controls

- HTTPS only
- WAF or DDoS protection
- upload rate limiting
- routine backups
- malware signature updates
- legal consent and privacy notice
- strong admin token rotation
