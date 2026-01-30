"""
YouTube Channel Library - Process Manager

Launches both backend (FastAPI) and frontend (Vite) servers with a single command.
Handles graceful shutdown when Ctrl+C is pressed.
"""

import subprocess
import signal
import sys
import time
import socket


processes = []


def is_port_in_use(port):
    """Check if a port is already in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(('127.0.0.1', port))
            return False
        except socket.error:
            return True


def signal_handler(sig, frame):
    """Handle Ctrl+C by terminating both processes cleanly."""
    print("\n[INFO] Shutting down servers...")
    for p in processes:
        try:
            p.terminate()
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
    print("[INFO] Shutdown complete")
    sys.exit(0)


def main():
    # Register signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    print("=" * 70)
    print("YouTube Channel Library - Starting servers")
    print("=" * 70)
    
    # Check if ports are available
    backend_port = 8000
    frontend_port = 5173
    
    if is_port_in_use(backend_port):
        print(f"[ERROR] Port {backend_port} is already in use.")
        print(f"[ERROR] Please stop the process using port {backend_port} and try again.")
        print(f"[HINT] Find the process with: lsof -ti:{backend_port}")
        print(f"[HINT] Kill it with: kill $(lsof -ti:{backend_port})")
        sys.exit(1)
    
    if is_port_in_use(frontend_port):
        print(f"[ERROR] Port {frontend_port} is already in use.")
        print(f"[ERROR] Please stop the process using port {frontend_port} and try again.")
        print(f"[HINT] Find the process with: lsof -ti:{frontend_port}")
        print(f"[HINT] Kill it with: kill $(lsof -ti:{frontend_port})")
        sys.exit(1)
    
    # Start backend server
    print(f"\n[BACKEND] Starting FastAPI server on http://127.0.0.1:{backend_port}")
    try:
        backend = subprocess.Popen(
            ["uvicorn", "main:app", "--reload"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        processes.append(backend)
    except FileNotFoundError:
        print("[ERROR] uvicorn not found. Make sure you have activated your virtual environment.")
        print("[ERROR] Run: source .venv/bin/activate")
        sys.exit(1)
    
    # Wait for backend to initialize
    print("[BACKEND] Waiting for server to start...")
    time.sleep(3)
    
    # Check if backend is still running
    if backend.poll() is not None:
        print("[ERROR] Backend failed to start. Check the error above.")
        sys.exit(1)
    
    print("[BACKEND] Server is ready")
    
    # Start frontend server
    print(f"\n[FRONTEND] Starting Vite dev server on http://localhost:{frontend_port}")
    try:
        frontend = subprocess.Popen(
            ["npm", "run", "dev"],
            cwd="frontend"
        )
        processes.append(frontend)
    except FileNotFoundError:
        print("[ERROR] npm not found. Make sure Node.js is installed.")
        backend.terminate()
        sys.exit(1)
    
    # Wait for frontend to initialize
    time.sleep(2)
    
    # Check if frontend is still running
    if frontend.poll() is not None:
        print("[ERROR] Frontend failed to start. Check the error above.")
        backend.terminate()
        sys.exit(1)
    
    print("[FRONTEND] Server is ready")
    
    print("\n" + "=" * 70)
    print("SERVERS RUNNING")
    print("=" * 70)
    print(f"Backend API:  http://127.0.0.1:{backend_port}")
    print(f"Frontend UI:  http://localhost:{frontend_port}")
    print("\nPress Ctrl+C to stop both servers")
    print("=" * 70)
    
    # Wait for processes to complete (they won't until interrupted)
    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        signal_handler(None, None)


if __name__ == "__main__":
    main()
