#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f .env ]]; then
  echo "Missing .env. Copy deploy/vultr.env.example to .env and fill it in first."
  exit 1
fi

docker compose build
docker compose up -d

echo
echo "Temple Twin containers:"
docker compose ps
echo
echo "Health check:"
curl --fail --silent --show-error http://127.0.0.1/health
echo
echo
echo "Deployment started successfully."
