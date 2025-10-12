# YouTube Channel Library

This is a full-stack application designed to fetch, store, and browse metadata for YouTube channels, playlists, and videos. It acts as a personal, local library for your favorite YouTube content, with a Python/FastAPI backend for data processing and a React frontend for a rich user experience.

## Features

- **Local Metadata Storage**: Fetches comprehensive data via `yt-dlp` and stores it in a local SQLite database.
- **Web Interface**: A modern React UI to browse and manage your library of channels, playlists, and videos.
- **URL Processing**: Simply paste a YouTube URL (channel, video, or playlist) to add it to your library.
- **Visual Browsing**: View your channels in a clean, card-based layout with thumbnails.
- **Detailed Views**: Click on a channel to see its detailed information and a list of all its videos stored in your library.


## Tech Stack

- **Backend**: Python, FastAPI, Uvicorn
- **Data Retrieval**: `yt-dlp`
- **Database**: SQLite
- **Frontend**: React, Vite, React-Bootstrap

## Setup and Installation

To get the project running locally, follow these steps.

### 1. Clone the Repository

```bash
git clone <repository-url>
cd retrieve_video_info_YouTube_channel
```

### 2. Backend Setup

From the project root directory, set up the Python virtual environment and install dependencies.

```bash
# Create and activate a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

### 3. Frontend Setup

Navigate to the `frontend` directory and install the Node.js dependencies.

```bash
cd frontend
npm install
```

## Configuration

The application can be configured by creating a `.env` file in the root of the project directory.

```
# .env file
DOWNLOAD_DIR=/path/to/your/desired/download/folder
```

- **`DOWNLOAD_DIR`**: Specifies the directory where video files will be downloaded. 
  - If this variable is not set, the application will default to using your system's standard `Downloads` folder.

- **Database Location**: The SQLite database file (`youtube.db`) will be automatically created inside the download directory (either the one you specified in `DOWNLOAD_DIR` or the default `Downloads` folder).

## Running the Application

This project requires two terminals running concurrently: one for the backend API and one for the frontend web server.

### Terminal 1: Start the Backend

Make sure you are in the project's root directory and your virtual environment is activated.

```bash
# If not activated
source .venv/bin/activate

# Run the FastAPI server with Uvicorn
uvicorn main:app --reload
```

This will start the backend API, typically available at `http://127.0.0.1:8000`.

### Terminal 2: Start the Frontend

In a new terminal, navigate to the `frontend` directory.

```bash
cd frontend

# Run the Vite development server
npm run dev
```

This will start the React application, which will automatically open in your browser, typically at `http://localhost:5173`.

Once both servers are running, you can use the web application to interact with the backend.
