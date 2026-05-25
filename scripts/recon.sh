#!/bin/bash
# Letta Code Windows 11 Connectivity Recon
# Run this on the Windows 11 machine to diagnose connectivity issues

set -e

echo "========================================"
echo "Letta Code Windows 11 Connectivity Recon"
echo "========================================"
echo ""
echo "Timestamp: $(date)"
echo ""

LETTA_HOST="10.0.0.143"
LETTA_API_PORT="8283"
LETTA_MEMFS_PORT="8285"

# ===== TEST 1: Basic System Info =====
echo "TEST 1: System Information"
echo "-----"
echo "Hostname: $(hostname)"
echo "Current user: $(whoami)"
echo "Working directory: $(pwd)"
echo ""

# ===== TEST 2: Network Interface =====
echo "TEST 2: Network Interfaces & Local IP"
echo "-----"
if command -v ip &> /dev/null; then
    LOCAL_IP=$(ip route | grep default | awk '{print $3}' | head -1)
    echo "Local gateway: $LOCAL_IP"
    echo "IPv4 addresses:"
    ip addr show | grep "inet " | grep -v "127.0.0.1" | awk '{print "  " $2}'
else
    echo "IPv4 addresses:"
    ifconfig 2>/dev/null | grep "inet " | grep -v "127.0.0.1" | awk '{print "  " $2}' || echo "  (ifconfig not available)"
fi
echo ""

# ===== TEST 3: Ping Letta Host =====
echo "TEST 3: Ping to Letta Host ($LETTA_HOST)"
echo "-----"
if ping -c 1 -W 2 $LETTA_HOST &> /dev/null; then
    echo "✅ PASS: $LETTA_HOST is reachable"
    PING_RESULT=$(ping -c 1 -W 2 $LETTA_HOST 2>&1 | grep "time=" | head -1)
    echo "  $PING_RESULT"
else
    echo "❌ FAIL: $LETTA_HOST is NOT reachable"
    echo "  Check if host is on network and IP is correct"
fi
echo ""

# ===== TEST 4: Port Connectivity (API) =====
echo "TEST 4: TCP Port $LETTA_API_PORT (Letta API) on $LETTA_HOST"
echo "-----"
if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$LETTA_HOST/$LETTA_API_PORT" 2>/dev/null; then
    echo "✅ PASS: Port $LETTA_API_PORT is accessible"
else
    echo "❌ FAIL: Port $LETTA_API_PORT is NOT accessible"
    echo "  Possible causes:"
    echo "  - Docker container not running"
    echo "  - docker-proxy process crashed"
    echo "  - Port mapping misconfigured"
    echo "  - Firewall blocking the port"
fi
echo ""

# ===== TEST 5: Port Connectivity (Memfs) =====
echo "TEST 5: TCP Port $LETTA_MEMFS_PORT (Letta Memfs) on $LETTA_HOST"
echo "-----"
if timeout 2 bash -c "cat < /dev/null > /dev/tcp/$LETTA_HOST/$LETTA_MEMFS_PORT" 2>/dev/null; then
    echo "✅ PASS: Port $LETTA_MEMFS_PORT is accessible"
else
    echo "❌ FAIL: Port $LETTA_MEMFS_PORT is NOT accessible"
fi
echo ""

# ===== TEST 6: HTTP API Response =====
echo "TEST 6: HTTP API Response from http://$LETTA_HOST:$LETTA_API_PORT/v1/health/"
echo "-----"
if command -v curl &> /dev/null; then
    API_RESPONSE=$(curl -s -m 5 "http://$LETTA_HOST:$LETTA_API_PORT/v1/health/" 2>&1)
    if echo "$API_RESPONSE" | grep -q "status"; then
        echo "✅ PASS: API is responding"
        echo "  Response: $API_RESPONSE"
    else
        echo "❌ FAIL: API not responding correctly"
        echo "  Response: $API_RESPONSE"
    fi
else
    echo "⚠️  curl not available, skipping HTTP test"
fi
echo ""

# ===== TEST 7: letta-code Configuration =====
echo "TEST 7: Letta Code Configuration"
echo "-----"
if [ -f ~/.letta/settings.json ]; then
    echo "Settings file found: ~/.letta/settings.json"
    if command -v python3 &> /dev/null; then
        LETTA_BASE_URL=$(python3 -c "import json; f=open(os.path.expanduser('~/.letta/settings.json')); data=json.load(f); print(data.get('LETTA_BASE_URL', 'NOT SET'))" 2>/dev/null || echo "Could not parse")
        echo "  LETTA_BASE_URL: $LETTA_BASE_URL"
    fi
    echo ""
    echo "Full settings.json (first 20 lines):"
    head -20 ~/.letta/settings.json | sed 's/^/  /'
else
    echo "Settings file not found at ~/.letta/settings.json"
fi
echo ""

# ===== TEST 8: Environment Variables =====
echo "TEST 8: Environment Variables"
echo "-----"
echo "LETTA_BASE_URL: ${LETTA_BASE_URL:-NOT SET}"
echo "LETTA_API_KEY: ${LETTA_API_KEY:-NOT SET}"
echo "OPENAI_API_KEY: ${OPENAI_API_KEY:-NOT SET}"
echo ""

# ===== TEST 9: Network Routing =====
echo "TEST 9: Network Routing to $LETTA_HOST"
echo "-----"
if command -v traceroute &> /dev/null; then
    echo "Traceroute to $LETTA_HOST (first 5 hops):"
    timeout 5 traceroute -m 5 $LETTA_HOST 2>&1 | head -6 | sed 's/^/  /'
elif command -v tracert &> /dev/null; then
    echo "Tracert to $LETTA_HOST:"
    timeout 5 tracert -h 5 $LETTA_HOST 2>&1 | head -6 | sed 's/^/  /'
else
    echo "traceroute/tracert not available"
fi
echo ""

# ===== TEST 10: DNS Resolution =====
echo "TEST 10: DNS Resolution for Hostname"
echo "-----"
if command -v nslookup &> /dev/null; then
    RESOLVED=$(nslookup localhost 2>&1 | grep "Address" | tail -1 || echo "Could not resolve")
    echo "localhost: $RESOLVED"
elif command -v getent &> /dev/null; then
    RESOLVED=$(getent hosts localhost 2>&1 | head -1 || echo "Could not resolve")
    echo "localhost: $RESOLVED"
fi
echo ""

# ===== TEST 11: letta-code Directory =====
echo "TEST 11: Letta Code Installation"
echo "-----"
if [ -d "$(pwd)" ]; then
    echo "Current directory: $(pwd)"
    echo "Directory contents:"
    ls -la | grep -E "^d|letta|package.json" | head -15 | sed 's/^/  /'

    if [ -f "package.json" ]; then
        echo ""
        echo "letta-code version:"
        grep '"version"' package.json | head -1 | sed 's/^/  /'
    fi
else
    echo "Current directory does not exist"
fi
echo ""

# ===== TEST 12: Node.js & npm =====
echo "TEST 12: Node.js & npm"
echo "-----"
if command -v node &> /dev/null; then
    echo "Node.js: $(node --version)"
else
    echo "Node.js: NOT INSTALLED"
fi
if command -v npm &> /dev/null; then
    echo "npm: $(npm --version)"
else
    echo "npm: NOT INSTALLED"
fi
echo ""

# ===== TEST 13: SSH Server Status =====
echo "TEST 13: SSH Server Status"
echo "-----"
CURRENT_USER=$(whoami)
echo "Current user: $CURRENT_USER"
if command -v sshd &> /dev/null; then
    echo "sshd binary: FOUND"
    if systemctl is-active --quiet sshd 2>/dev/null; then
        echo "sshd service: RUNNING"
        SSH_PORT=$(grep "^Port" /etc/ssh/sshd_config 2>/dev/null || echo "22")
        echo "SSH port: $SSH_PORT"
    else
        echo "sshd service: NOT RUNNING (try: sudo service ssh start)"
    fi
else
    echo "sshd binary: NOT FOUND (SSH not installed)"
fi
echo ""

# ===== TEST 14: Network Interface Details =====
echo "TEST 14: Detailed Network Information"
echo "-----"
echo "All IPv4 addresses:"
if command -v ip &> /dev/null; then
    ip addr show | grep "inet " | grep -v "127.0.0.1" | while read line; do
        echo "  $line"
    done
fi
echo ""
echo "Default gateway and routes:"
if command -v ip &> /dev/null; then
    ip route show | grep default | head -1
fi
echo ""
echo "Hostname/FQDN:"
hostname
echo ""

# ===== TEST 15: SSH Connection Command =====
echo "TEST 15: SSH Connection Information"
echo "-----"
PRIMARY_IP=$(ip addr show | grep "inet " | grep -v "127.0.0.1" | awk '{print $2}' | cut -d'/' -f1 | head -1)
echo "To SSH to this machine from another host:"
echo "  ssh $CURRENT_USER@$PRIMARY_IP"
echo ""
echo "Full command to run diagnostics remotely:"
echo "  ssh $CURRENT_USER@$PRIMARY_IP '/home/adamsl/letta-code/recon.sh'"
echo ""

# ===== SUMMARY =====
echo "========================================"
echo "SUMMARY"
echo "========================================"
echo ""
echo "Checklist:"
echo "☐ Ping to $LETTA_HOST succeeds"
echo "☐ TCP port $LETTA_API_PORT is accessible"
echo "☐ TCP port $LETTA_MEMFS_PORT is accessible"
echo "☐ HTTP API responds with valid JSON"
echo "☐ LETTA_BASE_URL is configured correctly"
echo "☐ letta-code is installed and working"
echo ""
echo "If API port test FAILS:"
echo "  - Check if Docker containers are running on $LETTA_HOST"
echo "  - Run: docker ps on the Windows 10 machine"
echo "  - Verify docker-proxy processes are active"
echo ""
echo "If API port test PASSES but HTTP fails:"
echo "  - Check if containers are healthy"
echo "  - Run: docker logs letta-server on the Windows 10 machine"
echo ""
echo "If LETTA_BASE_URL is not set:"
echo "  - Set it: export LETTA_BASE_URL=http://$LETTA_HOST:$LETTA_API_PORT"
echo "  - Or configure in ~/.letta/settings.json"
echo ""
echo "Report the results of these tests back to the main harness."
echo ""
