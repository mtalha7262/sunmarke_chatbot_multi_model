@echo off
echo ========================================
echo Sunmarke Voice RAG - Local Server
echo ========================================
echo.

REM Check if .env exists
if not exist .env (
    echo ERROR: .env file not found!
    echo Please copy env.example to .env and add your API keys
    echo.
    echo Run: copy env.example .env
    pause
    exit /b 1
)

REM Check if dependencies are installed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo Dependencies not found. Installing...
    echo.
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo ERROR: Failed to install dependencies
        echo Please check your Python installation and try again
        pause
        exit /b 1
    )
    echo.
    echo Dependencies installed successfully!
    echo.
)

REM Start the API server
echo Starting FastAPI server...
echo.
echo API will be available at: http://localhost:8000
echo API docs: http://localhost:8000/docs
echo Frontend: Open public/index.html in your browser
echo.
echo Press Ctrl+C to stop the server
echo.

cd api
if errorlevel 1 (
    echo ERROR: Could not change to api directory
    pause
    exit /b 1
)

python -m uvicorn index:app --host 0.0.0.0 --port 8000 --reload
