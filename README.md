# YouTube Channel & Video Manager

A Python tool to fetch, store, and manage information about YouTube channels and videos, including downloading media and transcripts.

*(Note: This project is a refactor of a previous version that used the YouTube Data API and MongoDB. It now utilizes `yt-dlp` and SQLite.)*

## Key Features (Current Version)

*   **Data Retrieval via `yt-dlp`**: Fetches channel and video metadata without requiring API keys.
*   **SQLite Storage**: Uses a simple file-based SQLite database (`youtube.db`) for storing information. (simple and effective)
*   **URL Parsing**: Handles various YouTube URL types (channel, video, playlist, shorts).
*   **Video Downloading**: Downloads videos to organized folders.
*   **Transcript Fetching**: Retrieves available video transcripts.
*   **Chapter Extraction**: Extracts video chapters/timestamps.
*   **Modular Design**: Code organized into classes for better maintainability (`YouTubeManager`, `SQLiteStorage`, `MediaDownloader`, etc.).
