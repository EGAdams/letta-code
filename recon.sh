#!/usr/bin/env bash
# recon.sh — gather info needed to set up SSH to the Letta server at 10.0.0.143

TARGET="10.0.0.143"

echo "=== Network connectivity ==="
ping -c 3 "$TARGET" 2>/dev/null || echo "ping failed (may be blocked by firewall)"

echo ""
echo "=== SSH port scan ==="
for port in 22 2222 22222; do
  if timeout 3 bash -c "echo >/dev/tcp/$TARGET/$port" 2>/dev/null; then
    echo "  port $port: OPEN"
  else
    echo "  port $port: closed/filtered"
  fi
done

echo ""
echo "=== Existing SSH keys on this machine ==="
ls ~/.ssh/*.pub 2>/dev/null || echo "  no public keys found in ~/.ssh/"
echo "  SSH config entries for $TARGET:"
grep -A5 "$TARGET" ~/.ssh/config 2>/dev/null || echo "  (none)"

echo ""
echo "=== Current user ==="
echo "  $(whoami)@$(hostname)"

echo ""
echo "=== SSH known_hosts entry for $TARGET ==="
grep "$TARGET" ~/.ssh/known_hosts 2>/dev/null || echo "  (no existing entry — first connection will prompt to trust host)"

echo ""
echo "=== Docker context (if Docker CLI is available) ==="
docker context ls 2>/dev/null || echo "  docker not in PATH"
docker -H "tcp://$TARGET:2375" ps 2>/dev/null && echo "  Docker daemon reachable on $TARGET:2375 (unauthenticated)" || echo "  Docker daemon not reachable on $TARGET:2375"

echo ""
echo "Done."
