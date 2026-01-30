# YouTube Channel Library

A full-stack application for building a personal, local library of YouTube content. Fetch and store metadata, transcripts, and video information from any YouTube channel, playlist, or video using a Python/FastAPI backend and React frontend.

## Features

- **URL-based intake**: Paste any YouTube URL (channel/video/playlist) to fetch and store metadata
- **Local storage**: SQLite database with cached thumbnails and complete metadata
- **Video transcripts**: Auto-fetched with chapter breakdown when available
- **AI Q&A**: Ask questions about video transcripts using Google GenAI (optional)
- **Media tracking**: Track downloads and manage local file paths
- **Refresh on demand**: Update video metadata and transcripts as needed

## Tech Stack

**Backend**: Python, FastAPI, Uvicorn, yt-dlp, SQLite  
**Frontend**: React, Vite, React-Bootstrap

## Installation

### Prerequisites

- Python 3.8+
- Node.js 16+

### Setup Steps

1. Clone the repository:
```bash
git clone <repository-url>
cd retrieve_video_info_YouTube_channel
```

2. Set up Python environment and dependencies:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Install frontend dependencies:
```bash
cd frontend
npm install
cd ..
```

## Configuration

Create a `.env` file in the project root (optional):

```bash
DOWNLOAD_DIR=/path/to/download/folder
GOOGLE_API_KEY=your_google_genai_api_key
```

**Configuration details:**
- `DOWNLOAD_DIR`: Where video files are downloaded. Defaults to system `Downloads` folder if not set.
- `GOOGLE_API_KEY`: Required only for AI transcript Q&A feature. Can be omitted if not needed.
- Database location: `youtube.db` is auto-created in the download directory.

## Running the Application

1. Activate your virtual environment:
```bash
source .venv/bin/activate
```

2. Start both servers:
```bash
python run.py
```

This launches:
- Backend API: `http://127.0.0.1:8000`
- Frontend UI: `http://localhost:5173`

3. Open `http://localhost:5173` in your browser to use the application.

4. Stop both servers with `Ctrl+C`.

### Troubleshooting

**Port conflicts**: If ports 8000 or 5173 are already in use:
```bash
# Find and kill process on port 8000
kill $(lsof -ti:8000)

# Find and kill process on port 5173
kill $(lsof -ti:5173)
```

