# YouTube Channel & Video Manager

A Python tool to fetch, store, and manage information about YouTube channels and videos, including downloading media and transcripts.

This project has been refactored into a modular and extensible architecture, moving away from a monolithic design. It now leverages `yt-dlp` for data retrieval and `SQLite` for efficient, file-based storage.

## Key Features

*   **Modular Design**: The codebase is organized into distinct, focused modules for improved maintainability, readability, and extensibility.
*   **`YouTubeClient`**: Serves as the primary entry point and orchestrator, coordinating operations across various components.
*   **Data Retrieval via `yt-dlp`**: Fetches channel and video metadata, transcripts, and chapters without requiring YouTube Data API keys.
*   **SQLite Storage**: Uses a simple file-based SQLite database (`youtube.db`) for persistent storage of channel, video, and playlist information.
*   **URL Parsing**: Intelligently handles various YouTube URL types (channel, video, playlist, shorts) to identify the primary entity.
*   **Video Downloading**: Downloads videos to organized, channel-specific folders.
*   **Transcript & Chapter Extraction**: Retrieves available video transcripts and extracts chapter information.

## Architecture Overview

The project is structured around a clear separation of concerns:

*   **`YouTubeClient`**: The top-level facade that integrates all other components. Users interact primarily with this class.
*   **Manager Classes**:
    *   `ChannelManager`: Handles all operations related to YouTube channels.
    *   `VideoManager`: Manages video-specific operations, including fetching details and downloading.
    *   `PlaylistManager`: Deals with YouTube playlists and their associated videos.
*   **Low-Level Utility Classes**:
    *   `InputParser`: Responsible for parsing YouTube URLs and extracting relevant IDs and entity types.
    *   `SQLiteStorage`: Provides an abstraction layer for all database interactions (CRUD operations for channels, videos, playlists, tags, and timestamps).
    *   `MediaDownloader`: Encapsulates the logic for interacting with `yt-dlp` to fetch raw data and download media.

This design ensures that each component has a single responsibility, making the system easier to understand, test, and expand.