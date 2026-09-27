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

health_ok=false
for attempt in {1..10}; do
  if curl --fail --silent --show-error http://127.0.0.1/health; then
    health_ok=true
    break
  fi

  echo
  echo "Health check attempt ${attempt}/10 failed; retrying in 2 seconds..."
  sleep 2
done

if [[ "${health_ok}" != "true" ]]; then
  echo
  echo "Health check failed after 10 attempts."
  exit 1
fi

echo
echo
echo "Deployment started successfully."
