# YouTube Channel & Video Information Retriever

This project is a Python application designed to fetch and store metadata, transcripts, and chapter information for YouTube channels, playlists, and videos. It operates by interfacing with `yt-dlp` for data retrieval and uses an SQLite database for local, persistent storage.

## Core Functionality

*   **Data Retrieval**: Fetches comprehensive data for YouTube channels, videos, and playlists without requiring the use of the YouTube Data API.
*   **Local Storage**: Organizes and stores all retrieved information in a local SQLite database, creating a structured library of the content.
*   **URL Processing**: Parses various YouTube URL formats (channel, video, playlist, shorts) to identify and process the corresponding entity.
*   **Content Extraction**: Capable of extracting video transcripts and chapter details when available.
*   **Media Downloading**: Includes functionality to download video files to a local, organized directory structure.

## Architectural Design

The system is designed with a modular architecture to separate concerns:

*   **`YouTubeClient`**: Acts as the primary interface and orchestrator for all operations.
*   **Manager Components**: High-level classes (`ChannelManager`, `VideoManager`, `PlaylistManager`) that manage the logic for their respective entities (channels, videos, playlists).
*   **Utility Components**: Low-level classes responsible for specific tasks:
    *   `InputParser`: Handles URL parsing and identification.
    *   `SQLiteStorage`: Manages all interactions with the SQLite database.
    *   `MediaDownloader`: Encapsulates data fetching and media download operations using `yt-dlp`.

This structure aims to provide a clear and maintainable codebase suitable for further development and extension.
