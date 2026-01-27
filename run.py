# run.py
"""
Enhanced script to run the FastAPI application and open browser
"""
import uvicorn
import sys
import os
import webbrowser
import time
from threading import Timer

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def open_browser():
    """Open browser after a short delay"""
    time.sleep(2)  # Wait for server to start
    webbrowser.open('http://localhost:8000')

if __name__ == "__main__":
    print("=" * 60)
    print("🚀 Starting Sunmarke Voice RAG API Server")
    print("=" * 60)
    print("📍 Local URL: http://localhost:8000")
    print("📍 API Docs: http://localhost:8000/docs")
    print("📍 Health Check: http://localhost:8000/health")
    print("=" * 60)
    print("\n✨ Opening browser automatically in 2 seconds...")
    print("Press CTRL+C to stop the server\n")
    
    # Open browser in a separate thread
    Timer(1, open_browser).start()
    
    # Start server
    uvicorn.run(
        "api.index:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )