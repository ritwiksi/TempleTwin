# Vultr deployment — Milestone 9

Milestone 9 deploys Temple Twin to a single Vultr Ubuntu server using Docker Compose.

Architecture:

```text
Internet :80
    |
    v
Nginx / React / Cesium
    |
    +-- /api/*  ---> FastAPI :8000 (private Docker network)
    +-- /health ---> FastAPI :8000
                       |
                       v
                   Tiger Cloud
```

The FastAPI container is not exposed directly to the public internet.

## 1. Create the Vultr server

Create a regular Vultr Cloud Compute instance with Ubuntu 24.04 LTS.

For this hackathon app, a small general-purpose instance is sufficient. The app
does not require a GPU because Cesium rendering happens in the user's browser.

Add your SSH key when creating the instance.

## 2. Firewall

Allow:

- TCP 22 for SSH
- TCP 80 for HTTP

HTTPS/443 is Milestone 10.

If using UFW on the server:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw enable
```

## 3. Install Docker

Follow Vultr's Ubuntu 24.04 Docker instructions. The required packages are:

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

Log out and SSH back in after adding yourself to the docker group.

## 4. Clone Temple Twin

```bash
git clone https://github.com/ritwiksi/TempleTwin.git
cd TempleTwin
```

## 5. Configure production secrets

```bash
cp deploy/vultr.env.example .env
nano .env
```

Fill in:

```env
VITE_CESIUM_ION_TOKEN=...
DATABASE_URL=postgresql://...?...sslmode=require
```

Do not commit this file.

The Cesium token is compiled into the browser application, so scope/restrict that
token in Cesium ion. The Tiger connection string stays server-side only.

## 6. Deploy

```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh
```

## 7. Verify

From the server:

```bash
curl http://127.0.0.1/health
curl http://127.0.0.1/api/buildings/serc/profile
```

From your computer open:

```text
http://YOUR_VULTR_PUBLIC_IP
```

Then verify:

1. Temple campus loads.
2. Reality / Energy works.
3. Energy profiles load from Tiger.
4. Building details open.
5. LED/HVAC/solar interventions update the selected building.
6. Refreshing the public IP still loads the app.

## Updating the deployment

After future commits:

```bash
cd TempleTwin
git pull
./deploy/deploy.sh
```

## Milestone 9 boundaries

This milestone intentionally uses HTTP on the server IP.

Custom domain + HTTPS are Milestone 10.
