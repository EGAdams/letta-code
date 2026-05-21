  # Step 1 — Build (5-10 min)
  # cd /home/adamsl/letta-src && docker build -t letta-from-source:latest . 2>&1 | tail -20

  # Step 2 — Restart letta-server only
  docker compose -f /home/adamsl/letta-src/docker-compose.prod.yml up -d --no-deps letta

  # Step 3 — Confirm startup (wait ~35s first)
  sleep 35 && docker logs letta-server --tail 20

  # Step 4 — Health check
  curl -s http://localhost:8283/v1/health/

  # Step 5 — Restart letta-bridge (required after every letta-server restart)
  docker stop letta-bridge && docker rm letta-bridge
  docker compose -f /home/adamsl/letta-src/docker-compose.prod.yml up -d letta-bridge
  curl -s http://127.0.0.1:18283/v1/health/
