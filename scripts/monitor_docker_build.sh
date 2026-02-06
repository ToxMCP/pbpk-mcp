#!/usr/bin/env bash
# Monitor Docker build progress and provide status updates

LOG_FILE="/tmp/docker_build_ospsuite.log"
CHECK_INTERVAL=10

echo "Monitoring Docker build progress..."
echo "Log file: $LOG_FILE"
echo ""

while true; do
    if [ -f "$LOG_FILE" ]; then
        # Check for completion
        if grep -q "Successfully tagged mcp-bridge:amd64" "$LOG_FILE"; then
            echo "✅ Build completed successfully!"
            tail -5 "$LOG_FILE"
            exit 0
        fi
        
        # Check for errors
        if grep -q "ERROR" "$LOG_FILE"; then
            echo "❌ Build failed with errors:"
            grep "ERROR" "$LOG_FILE" | tail -5
            exit 1
        fi
        
        # Show current progress
        LAST_STEP=$(grep "^#" "$LOG_FILE" | tail -1)
        echo "[$(date +%H:%M:%S)] $LAST_STEP"
    else
        echo "Waiting for build to start..."
    fi
    
    sleep $CHECK_INTERVAL
done
