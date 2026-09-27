# Temple Twin production deployment

Temple Twin is designed to run on one Ubuntu server with Docker Compose.

```text
Browser
  |
  | HTTP/HTTPS
  v
Nginx + React + Cesium
  |
  +-- /api/*  ---> FastAPI :8000 (private Docker network)
  +-- /health ---> FastAPI :8000
                       |
                       +--> Tiger Data / PostgreSQL
                       |
                       +--> Snowflake Cortex
```

FastAPI is not exposed directly to the public internet. The frontend uses same-origin
`/api/*` requests in production, so nginx forwards API traffic internally.

## Before creating the server

Have these values ready:

- `VITE_CESIUM_ION_TOKEN`
- `DATABASE_URL`
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_PASSWORD`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
- `SNOWFLAKE_ROLE`
- `SNOWFLAKE_CORTEX_MODEL`

For production, use the `TEMPLE_TWIN_APP` role defined in
`deploy/snowflake_role.sql` instead of `ACCOUNTADMIN`.

## 1. Create the Vultr server

Create a regular Vultr Cloud Compute instance with Ubuntu 24.04 LTS and add your SSH
key. Temple Twin does not need a GPU; Cesium rendering happens in the user's browser.

Allow TCP 22, 80, and eventually 443.

If using UFW:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
```

## 2. Install Docker

```bash
sudo apt update
sudo apt install -y ca-certificates curl

sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
$(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Log out and SSH back in after adding yourself to the Docker group.

## 3. Clone and configure

```bash
git clone https://github.com/ritwiksi/TempleTwin.git
cd TempleTwin
cp deploy/vultr.env.example .env
nano .env
```

Fill in every required value. Keep:

```env
ENABLE_DIAGNOSTICS=false
```

The populated `.env` must never be committed.

## 4. Deploy

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

Useful checks:

```bash
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=100 frontend
curl -f http://127.0.0.1/health
curl -f http://127.0.0.1/api/simulation
```

Then open:

```text
http://YOUR_VULTR_PUBLIC_IP
```

Verify Reality mode, Energy mode, building search, timeline playback, interventions,
and Ask Temple Twin.

## 5. Verify external services from Vultr

Tiger:

```bash
curl -f http://127.0.0.1/health
```

Ask Temple Twin should be tested through the app. If troubleshooting is necessary,
temporarily set `ENABLE_DIAGNOSTICS=true`, rebuild/restart, and request:

```text
/api/ask-temple-twin/status
```

Set it back to `false` afterward.

## 6. Domain and HTTPS

Point an A record such as `templetwin.example.com` to the Vultr IPv4 address.

For the simplest hackathon setup, install Certbot on the host and terminate HTTPS
in a host-level reverse proxy, or adapt the nginx container to mount certificates.
Do not request a certificate until DNS resolves to the server.

Host-level nginx/Certbot option:

```bash
sudo apt install -y nginx certbot python3-certbot-nginx
```

If using host nginx, change the Docker frontend port mapping from `80:80` to a
loopback-only high port such as `127.0.0.1:8080:80`, then proxy the domain to
`http://127.0.0.1:8080`.

Example host nginx site:

```nginx
server {
    listen 80;
    server_name templetwin.example.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then:

```bash
sudo nginx -t
sudo systemctl reload nginx
sudo certbot --nginx -d templetwin.example.com
```

After HTTPS is active, verify:

- frontend loads over HTTPS;
- `/health` works;
- `/api/*` works on the same origin;
- Cesium/Google Photorealistic 3D Tiles render;
- Tiger-backed energy data loads;
- Ask Temple Twin returns a Cortex response.

## Updating production

```bash
cd TempleTwin
git pull origin main
./deploy/deploy.sh
```

## Production smoke test

1. Open Reality mode and reset the camera.
2. Switch to Energy.
3. Search for SERC.
4. Open a building by direct map click.
5. Move the timeline across midnight and several days.
6. Toggle LED, HVAC, solar, and all three together.
7. Confirm solar panels appear/disappear.
8. Ask Temple Twin a campus-wide question.
9. Ask Temple Twin a building-specific question.
10. Refresh the page and repeat one API-backed interaction.
