#!/bin/bash
# Letta Code Error Capture and Reporting
# Run on Windows 11 machine to capture all error details

OUTPUT_FILE="/tmp/letta-error-report.txt"

# Create output file
cat > "$OUTPUT_FILE" << 'EOF'
========================================
LETTA CODE ERROR REPORT
========================================

Timestamp: EOF
date >> "$OUTPUT_FILE"
cat >> "$OUTPUT_FILE" << 'EOF'
Machine: EOF
hostname >> "$OUTPUT_FILE"
cat >> "$OUTPUT_FILE" << 'EOF'
Working Directory: EOF
pwd >> "$OUTPUT_FILE"
cat >> "$OUTPUT_FILE" << 'EOF'
User: EOF
whoami >> "$OUTPUT_FILE"
cat >> "$OUTPUT_FILE" << 'EOF'

========================================
SECTION 1: Letta Code Settings
========================================
EOF

if [ -f ~/.letta/settings.json ]; then
    echo "Settings file found at ~/.letta/settings.json" >> "$OUTPUT_FILE"
    echo "File size: $(wc -c < ~/.letta/settings.json) bytes" >> "$OUTPUT_FILE"
    echo "" >> "$OUTPUT_FILE"
    echo "Full content:" >> "$OUTPUT_FILE"
    cat ~/.letta/settings.json >> "$OUTPUT_FILE" 2>&1
else
    echo "ERROR: Settings file not found at ~/.letta/settings.json" >> "$OUTPUT_FILE"
fi

cat >> "$OUTPUT_FILE" << 'EOF'

========================================
SECTION 2: Environment Variables
========================================
EOF

echo "All environment variables:" >> "$OUTPUT_FILE"
env | sort >> "$OUTPUT_FILE" 2>&1

cat >> "$OUTPUT_FILE" << 'EOF'

Letta-related variables:" >> "$OUTPUT_FILE"
env | grep -i letta >> "$OUTPUT_FILE" 2>&1 || echo "  (none found)" >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" << 'EOF'

========================================
SECTION 3: Node.js & npm Status
========================================
EOF

echo "Node version:" >> "$OUTPUT_FILE"
node --version >> "$OUTPUT_FILE" 2>&1

echo "npm version:" >> "$OUTPUT_FILE"
npm --version >> "$OUTPUT_FILE" 2>&1

cat >> "$OUTPUT_FILE" << 'EOF'

Running Node processes:" >> "$OUTPUT_FILE"
ps aux | grep node | grep -v grep >> "$OUTPUT_FILE" 2>&1 || echo "  (no node processes found)" >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" << 'EOF'

========================================
SECTION 4: Letta Code Directory
========================================
EOF

echo "Directory listing of /home/adamsl/letta-code:" >> "$OUTPUT_FILE"
ls -la /home/adamsl/letta-code 2>&1 | head -30 >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" << 'EOF'

Key files:" >> "$OUTPUT_FILE"
if [ -f package.json ]; then
    echo "  package.json: EXISTS" >> "$OUTPUT_FILE"
    grep '"version"' package.json | head -1 >> "$OUTPUT_FILE"
else
    echo "  package.json: MISSING" >> "$OUTPUT_FILE"
fi

if [ -f dist/index.js ]; then
    echo "  dist/index.js: EXISTS" >> "$OUTPUT_FILE"
else
    echo "  dist/index.js: MISSING (need to rebuild?)" >> "$OUTPUT_FILE"
fi

cat >> "$OUTPUT_FILE" << 'EOF'

========================================
SECTION 5: .letta Directory Contents
========================================
EOF

if [ -d ~/.letta ]; then
    echo "Contents of ~/.letta/:" >> "$OUTPUT_FILE"
    ls -la ~/.letta/ 2>&1 >> "$OUTPUT_FILE"
else
    echo "ERROR: ~/.letta directory not found" >> "$OUTPUT_FILE"
fi

cat >> "$OUTPUT_FILE" << 'EOF'

========================================
SECTION 6: .letta/sessions (if exists)
========================================
EOF

if [ -d ~/.letta/sessions ]; then
    echo "Sessions directory contents:" >> "$OUTPUT_FILE"
    ls -la ~/.letta/sessions/ 2>&1 | head -20 >> "$OUTPUT_FILE"
else
    echo "No sessions directory found" >> "$OUTPUT_FILE"
fi

cat >> "$OUTPUT_FILE" << 'EOF'

========================================
SECTION 7: Recent Commands in letta-code
========================================
EOF

echo "Recent git commits:" >> "$OUTPUT_FILE"
if [ -d /home/adamsl/letta-code/.git ]; then
    cd /home/adamsl/letta-code
    git log --oneline -10 2>&1 >> "$OUTPUT_FILE"
else
    echo "Not a git repository" >> "$OUTPUT_FILE"
fi

cat >> "$OUTPUT_FILE" << 'EOF'

========================================
SECTION 8: Network Status
========================================
EOF

echo "Network interfaces:" >> "$OUTPUT_FILE"
ip addr show | grep inet >> "$OUTPUT_FILE" 2>&1

echo "" >> "$OUTPUT_FILE"
echo "DNS resolution:" >> "$OUTPUT_FILE"
cat /etc/resolv.conf 2>&1 | head -10 >> "$OUTPUT_FILE"

echo "" >> "$OUTPUT_FILE"
echo "Connectivity to Letta server:" >> "$OUTPUT_FILE"
curl -s -m 5 http://10.0.0.143:8283/v1/health/ >> "$OUTPUT_FILE" 2>&1

cat >> "$OUTPUT_FILE" << 'EOF'

========================================
SECTION 9: System Resources
========================================
EOF

echo "Memory usage:" >> "$OUTPUT_FILE"
free -h >> "$OUTPUT_FILE" 2>&1

echo "" >> "$OUTPUT_FILE"
echo "Disk usage (home directory):" >> "$OUTPUT_FILE"
du -sh /home/adamsl 2>&1 >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" << 'EOF'

========================================
SECTION 10: letta-code Build Status
========================================
EOF

cd /home/adamsl/letta-code 2>&1
echo "Last build/modification times:" >> "$OUTPUT_FILE"
echo "  dist/: $(stat -c %y dist/ 2>/dev/null || echo 'N/A')" >> "$OUTPUT_FILE"
echo "  src/: $(stat -c %y src/ 2>/dev/null || echo 'N/A')" >> "$OUTPUT_FILE"
echo "  node_modules/: $(stat -c %y node_modules/ 2>/dev/null || echo 'N/A')" >> "$OUTPUT_FILE"

cat >> "$OUTPUT_FILE" << 'EOF'

========================================
END OF REPORT
========================================
EOF

# Display summary and copy instructions
echo ""
echo "========================================"
echo "Report Generated!"
echo "========================================"
echo ""
echo "Output saved to: $OUTPUT_FILE"
echo ""
echo "To copy to Windows 10 Desktop:"
echo "  cp $OUTPUT_FILE /mnt/c/Users/NewUser/Desktop/"
echo ""
echo "Report size: $(wc -c < "$OUTPUT_FILE") bytes"
echo ""
echo "First 50 lines:"
head -50 "$OUTPUT_FILE"
echo ""
echo "... (full report saved to $OUTPUT_FILE)"
echo ""

