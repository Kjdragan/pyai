🛠 One-pager for the pair-programmer
Goal: Make the database UI that runs in a Docker container reachable from any web app without tripping Microsoft Edge’s new Private Network Access (PNA) block.
Chosen fix: Terminate TLS + add the required Access-Control-Allow-Private-Network: true header with a lightweight reverse-proxy (Caddy). It’s one container, zero code-mods to the DB image, and keeps us future-proof when the browser policies become non-optional.

1 · Folder layout
pgsql
Copy
Edit
project-root/
 ├─ compose.yaml
 ├─ Caddyfile         # reverse-proxy rules
 └─ certs/            # mkcert-generated local CA + cert/key (git-ignored)
2 · compose.yaml (v3.9)
yaml
Copy
Edit
version: "3.9"

services:
  db-admin:
    image: adminer:latest          # or your pgAdmin/Metabase/etc.
    restart: unless-stopped
    networks: [ backend ]

  caddy:
    image: caddy:2.8-alpine
    restart: unless-stopped
    ports:
      - "443:443"                  # expose HTTPS to host
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - ./certs:/data/caddy/pki     # mkcert certs live here
    networks: [ backend ]

networks:
  backend:
3 · Caddyfile
caddyfile
Copy
Edit
{
	# Global options
	auto_https disable_redirects    # we’ll hit https://localhost directly
}

https://localhost {
	encode zstd gzip

	# Satisfy PNA pre-flight
	header Access-Control-Allow-Private-Network "true"

	# Pass everything else to the DB UI
	reverse_proxy db-admin:8080
}
Why the header?
Edge / Chrome (≥ 117) send an OPTIONS pre-flight with
Access-Control-Request-Private-Network: true when a public page fetches https://localhost:*.
Returning Access-Control-Allow-Private-Network: true is the handshake that lets the real request proceed.
Chrome for Developers

4 · Generate a localhost cert the browser trusts
bash
Copy
Edit
mkcert -install
mkcert -key-file certs/localhost-key.pem -cert-file certs/localhost.pem localhost
Caddy auto-detects the files in /data/caddy/pki and serves https://localhost with them.

5 · Run it
bash
Copy
Edit
docker compose up -d
open https://localhost       # macOS
start https://localhost      # Windows
You’ll see the DB UI, PNA pre-flight passes, and the old “localhost is blocked” splash is gone.

6 · Smoke test (optional)
bash
Copy
Edit
curl -I --resolve localhost:443:127.0.0.1 https://localhost \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Private-Network: true" \
  -H "Access-Control-Request-Method: GET"
Expect HTTP/1.1 204 No Content plus
Access-Control-Allow-Private-Network: true.

7 · Why we didn’t just “disable the flag”
Edge’s BlockInsecurePrivateNetworkRequests flag and the InsecurePrivateNetworkRequestsAllowed* GPO keys become obsolete after Edge 137. Your future self (or a user) will eventually be forced back on.
Microsoft Learn

Adjusting the service once beats debugging mysteriously-blocked requests later.

8 · TL;DR for the reviewer
Add a Caddy sidecar that speaks HTTPS on localhost:443, forwards to the existing DB container, and injects Access-Control-Allow-Private-Network: true. Zero app-code changes, survives the upcoming hard-enforcement in Chromium browsers. Docs pinned above; yell if you’d rather proxy with Traefik 3.0 – config is almost identical.

FYI: timeline of the breakage
Chrome / Edge 117 (Sept 2023) – PNA enforcement turned on for public→private sub-resource fetches.
Chrome for Developers

Edge 137 (Q4 2025) – admin policies to disable it are marked obsolete.
Microsoft Learn

Edge wasn’t singling out Docker; it was just the first time your setup crossed a public→private boundary after the update.
