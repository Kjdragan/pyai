#!/bin/bash
# Start script for PyAI with PNA fix
# Starts both the Streamlit app and Caddy proxy

set -e

echo "🚀 Starting PyAI with PNA fix..."

# Check if certificates exist
if [[ ! -f "certs/localhost.pem" ]] || [[ ! -f "certs/localhost-key.pem" ]]; then
    echo "❌ SSL certificates not found. Please run './setup-pna-fix.sh' first."
    exit 1
fi

# Create logs directory if it doesn't exist
mkdir -p logs

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    
    # Kill Caddy
    if [[ -n "$CADDY_PID" ]]; then
        kill $CADDY_PID 2>/dev/null || true
        echo "✅ Caddy stopped"
    fi
    
    # Kill Streamlit
    if [[ -n "$STREAMLIT_PID" ]]; then
        kill $STREAMLIT_PID 2>/dev/null || true
        echo "✅ Streamlit stopped"
    fi
    
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM EXIT

# Start Caddy in background
echo "🌐 Starting Caddy proxy..."
caddy run --config Caddyfile &
CADDY_PID=$!
sleep 2

# Check if Caddy started successfully
if ! kill -0 $CADDY_PID 2>/dev/null; then
    echo "❌ Failed to start Caddy"
    exit 1
fi
echo "✅ Caddy proxy started (PID: $CADDY_PID)"

# Activate virtual environment and start Streamlit
echo "🎯 Starting Streamlit app..."
cd src

# Check if we're in WSL/Linux and use python3
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

# Start Streamlit in background
../.venv/bin/python3 -m streamlit run streamlit_app.py --server.port=8501 --server.address=localhost &
STREAMLIT_PID=$!
sleep 3

# Check if Streamlit started successfully
if ! kill -0 $STREAMLIT_PID 2>/dev/null; then
    echo "❌ Failed to start Streamlit"
    exit 1
fi
echo "✅ Streamlit app started (PID: $STREAMLIT_PID)"

echo ""
echo "🎉 PyAI is now running with PNA fix!"
echo ""
echo "📍 Access URLs:"
echo "  🔒 HTTPS (PNA-fixed): https://localhost:8443"
echo "  🔓 HTTP (direct):     http://localhost:8501"
echo ""
echo "💡 Use the HTTPS URL to avoid PNA errors when accessing from public websites"
echo "📝 Logs are saved in logs/caddy.log"
echo ""
echo "Press Ctrl+C to stop all services..."

# Wait for user interrupt
wait
