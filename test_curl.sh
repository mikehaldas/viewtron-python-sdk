#!/bin/bash
# Test ViewtronEvent by POSTing fixture XML files to the test server
PORT=5050
EXAMPLES="/Users/admin/Claude/IP-Camera-API/examples"

echo "=== LPR IPC ==="
curl -s -X POST http://localhost:$PORT -H "Content-Type: application/xml" -d @$EXAMPLES/ipc-v1x/lpr.xml > /dev/null
sleep 0.3

echo "=== LPR NVR ==="
curl -s -X POST http://localhost:$PORT -H "Content-Type: application/xml" -d @$EXAMPLES/nvr-v2/vehicle-lpr.xml > /dev/null
sleep 0.3

echo "=== Face NVR ==="
curl -s -X POST http://localhost:$PORT -H "Content-Type: application/xml" -d @$EXAMPLES/nvr-v2/face-detection.xml > /dev/null
sleep 0.3

echo "=== Intrusion IPC ==="
curl -s -X POST http://localhost:$PORT -H "Content-Type: application/xml" -d @$EXAMPLES/ipc-v1x/perimeter-intrusion.xml > /dev/null
sleep 0.3

echo "=== Keepalive (should skip) ==="
curl -s -X POST http://localhost:$PORT -H "Content-Type: application/xml" -d @$EXAMPLES/ipc-v1x/keepalive.xml > /dev/null
sleep 0.3

echo "=== Counting NVR ==="
curl -s -X POST http://localhost:$PORT -H "Content-Type: application/xml" -d @$EXAMPLES/nvr-v2/target-counting-by-line.xml > /dev/null
sleep 0.3

echo "=== DONE ==="
