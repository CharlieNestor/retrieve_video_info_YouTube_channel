# YouTube Channel Library

This is a full-stack application designed to fetch, store, and browse metadata for YouTube channels, playlists, and videos. It acts as a personal, local library for your favorite YouTube content, with a Python/FastAPI backend for data processing and a React frontend for a rich user experience.

## Features

- **Local SQLite Library**: Fetch rich metadata via `yt-dlp` and store it locally.
- **URL Intake**: Paste a channel, video, or playlist URL to add entries.
- **Channel Browser UI**: Grid of channels with cached thumbnails (via image proxy).
- **Video Details**: Views, likes, duration, publish date, tags, and description.
- **Transcripts**: Plain text plus chapter breakdown when available.
- **Ask the Transcript**: Chat-style Q&A over the video’s transcript.
- **One‑click Refresh**: Update a video’s metadata and transcript on demand.
- **Download Awareness**: See downloaded state and copy the local file path.


## Tech Stack

- **Backend**: Python, FastAPI, Uvicorn
- **Data Retrieval**: `yt-dlp`
- **Database**: SQLite
- **Frontend**: React, Vite, React-Bootstrap
- **Markdown Rendering**: `react-markdown` with `remark-gfm` for formatted LLM responses

## Setup

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
python3 -m venv .venv
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
GOOGLE_API_KEY=your_google_genai_api_key
```

- **`DOWNLOAD_DIR`**: Specifies the directory where video files will be downloaded. 
  - If this variable is not set, the application will default to using your system's standard `Downloads` folder.

- **`GOOGLE_API_KEY`**: Enables the “Ask the Transcript” feature. If omitted, LLM Q&A is disabled.

- **Database Location**: The SQLite database file (`youtube.db`) will be automatically created inside the download directory (either the one you specified in `DOWNLOAD_DIR` or the default `Downloads` folder).

## Running the Application

Note: this project currently runs in two terminals (backend + frontend) because it’s still a work in progress. We plan to streamline this.

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
