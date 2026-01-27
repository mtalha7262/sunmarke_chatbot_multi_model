#!/bin/bash

echo "========================================"
echo "Sunmarke Voice RAG - Local Server"
echo "========================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "ERROR: .env file not found!"
    echo "Please copy env.example to .env and add your API keys"
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "WARNING: Virtual environment not detected"
    echo "It's recommended to use a virtual environment"
    echo ""
fi

# Start the API server
echo "Starting FastAPI server..."
echo ""
echo "API will be available at: http://localhost:8000"
echo "Frontend: Open public/index.html in your browser"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

cd api
python -m uvicorn index:app --host 0.0.0.0 --port 8000 --reload
