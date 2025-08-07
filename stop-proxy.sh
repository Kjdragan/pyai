#!/bin/bash
# Stop script for PyAI proxy services
# Stops both Caddy and Streamlit processes

echo "🛑 Stopping PyAI services..."

# Function to find and kill processes by name
kill_process() {
    local process_name=$1
    local pids=$(pgrep -f "$process_name" 2>/dev/null || true)
    
    if [[ -n "$pids" ]]; then
        echo "Stopping $process_name processes: $pids"
        kill $pids 2>/dev/null || true
        sleep 2
        
        # Force kill if still running
        local remaining_pids=$(pgrep -f "$process_name" 2>/dev/null || true)
        if [[ -n "$remaining_pids" ]]; then
            echo "Force stopping $process_name processes: $remaining_pids"
            kill -9 $remaining_pids 2>/dev/null || true
        fi
        echo "✅ $process_name stopped"
    else
        echo "ℹ️  No $process_name processes found"
    fi
}

# Stop Caddy
kill_process "caddy"

# Stop Streamlit
kill_process "streamlit"

echo "✅ All services stopped"
