import sqlite3
import requests
import os
import hashlib
import time
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from youtube_client import YouTubeClient


# Define a Pydantic model for the request body
# This ensures that any request to the endpoint must have a 'url' field that is a string.
class URLItem(BaseModel):
    url: str

# Initialize the FastAPI application
app = FastAPI(
    title="YouTube Channel Retriever API",
    description="An API to interact with the YouTube channel data library.",
    version="1.0.0"
)

# Set up CORS (Cross-Origin Resource Sharing)
origins = [
    "http://localhost:5173",  # Allow the frontend development server
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Instantiate the YouTubeClient
# This single client instance will be shared across all API requests.
client = YouTubeClient()


@app.get("/api/image-proxy")
def image_proxy(url: str = Query(...)):
    """
    Acts as a proxy for fetching images from external URLs.
    This helps to avoid client-side rate-limiting issues and handles thumbnail fallbacks.
    It also uses a 7-day TTL disk cache to improve performance and reduce requests.
    """
    # --- Caching Configuration ---
    cache_dir = os.path.join(client.downloader.download_dir, "image_cache")
    os.makedirs(cache_dir, exist_ok=True)
    cache_ttl_seconds = 7 * 24 * 60 * 60  # 7 days

    # Generate a safe filename from the URL
    url_hash = hashlib.sha256(url.encode('utf-8')).hexdigest()
    # Try to get a file extension, default to .jpg
    file_extension = os.path.splitext(url.split('?')[0])[-1] or '.jpg'
    if not file_extension.startswith('.'):
        file_extension = '.jpg' # Fallback for URLs without clear extensions
    cache_path = os.path.join(cache_dir, f"{url_hash}{file_extension}")

    # --- Cache Check ---
    if os.path.exists(cache_path):
        file_age = time.time() - os.path.getmtime(cache_path)
        if file_age < cache_ttl_seconds:
            return FileResponse(cache_path)

    # --- Fetching Logic (if cache miss or stale) ---
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    thumbnail_qualities = ['maxresdefault.jpg', 'hqdefault.jpg', 'sddefault.jpg', 'mqdefault.jpg']
    is_yt_thumbnail = 'i.ytimg.com' in url

    urls_to_try = [url]
    if is_yt_thumbnail:
        for quality in thumbnail_qualities:
            if quality in url:
                base_url = url.rsplit('/', 1)[0]
                urls_to_try = list(dict.fromkeys([url] + [f"{base_url}/{q}" for q in thumbnail_qualities]))
                break

    for attempt_url in urls_to_try:
        try:
            response = requests.get(attempt_url, stream=True, headers=headers)
            if response.status_code == 200:
                # --- Save to Cache and Serve ---
                with open(cache_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                
                return FileResponse(cache_path)

            if response.status_code == 404 and len(urls_to_try) > 1:
                continue
            
            response.raise_for_status()
        except requests.exceptions.RequestException:
            if attempt_url == urls_to_try[-1]:
                raise
            else:
                continue

    raise HTTPException(status_code=502, detail="Failed to fetch image from any of the fallback URLs.")


@app.post("/api/url", status_code=201)
def process_url(item: URLItem):
    """
    Processes a YouTube URL to fetch and store its metadata.

    - **url**: The YouTube URL to process (channel, video, or playlist).
    """
    try:
        result = client.process_url(item.url)
        if not result:
            raise HTTPException(status_code=404, detail="Could not retrieve any information from the provided URL.")
        return result
    except ValueError as e:
        # This catches errors from the URL parser if the URL is invalid.
        raise HTTPException(status_code=422, detail=f"Invalid URL provided: {e}")
    except Exception as e:
        # This is a general catch-all for other unexpected errors.
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


##### CHANNEL ENDPOINTS #####


@app.get("/api/channels")
def list_channels():
    """
    Retrieves a list of all channels stored in the database.
    This endpoint calls the corresponding method in the ChannelManager.
    """
    try:
        return client.channel_manager.list_channels()
    except sqlite3.Error as e:
        # If a database error occurs, return a 500 Internal Server Error
        # with a clear error message.
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        # Catch any other unexpected errors.
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
    

@app.get("/api/channels/{channel_id}")
def get_channel(channel_id: str):
    """
    Retrieves detailed information for a specific channel.

    - **channel_id**: The unique ID of the channel to retrieve.
    """
    try:
        channel = client.channel_manager.get_channel(channel_id)
        if channel is None:
            # The backend returned None, so the channel was not found.
            raise HTTPException(status_code=404, detail=f"Channel with id '{channel_id}' not found.")
        return channel
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.get("/api/channels/{channel_id}/videos")
def get_channel_videos(channel_id: str):
    """
    Retrieves a list of videos for a specific channel.

    - **channel_id**: The unique ID of the channel.
    """
    try:
        return client.channel_manager.get_channel_videos(channel_id)
    except ValueError as e:
        # This will catch the "Channel not found" error.
        raise HTTPException(status_code=404, detail=str(e))
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.delete("/api/channels/{channel_id}", status_code=200)
def delete_channel(channel_id: str):
    """
    Deletes a channel and all of its associated data.

    - **channel_id**: The ID of the channel to delete.
    """
    try:
        client.channel_manager.delete_channel(channel_id)
        return {"message": f"Channel '{channel_id}' and all associated data deleted successfully."}
    except ValueError as e:
        # This catches the "not found" or "empty id" error from the manager.
        raise HTTPException(status_code=404, detail=str(e))
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.get("/api/channels/{channel_id}/playlists")
def get_channel_playlists(channel_id: str, limit: int = None, sort_by: str = "title"):
    """
    Retrieves a list of playlists for a specific channel.

    - **channel_id**: The unique ID of the channel.
    - **limit**: The maximum number of playlists to return.
    - **sort_by**: The sorting criteria ('title', 'video_count').
    """
    try:
        return client.channel_manager.get_channel_playlists(channel_id, limit=limit, sort_by=sort_by)
    except ValueError as e:
        # Catches errors like non-existent channel or empty channel_id.
        raise HTTPException(status_code=404, detail=str(e))
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.get("/api/channels/{channel_id}/tags")
def get_channel_tags(channel_id: str, limit: int = None, min_video_count: int = 1):
    """
    Retrieves unique tags for a channel from the local database.

    - **channel_id**: The ID of the channel.
    - **limit**: The maximum number of unique tags to return.
    - **min_video_count**: The minimum number of videos a tag must be associated with.
    """
    try:
        return client.channel_manager.get_channel_tags(channel_id, limit=limit, min_video_count=min_video_count)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


##### VIDEO ENDPOINTS #####


@app.get("/api/videos")
def list_videos():
    """
    Retrieves a list of all videos stored in the database.
    """
    try:
        return client.video_manager.list_all_videos()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.get("/api/videos/{video_id}")
def get_video(video_id: str):
    """
    Retrieves detailed information for a specific video.

    - **video_id**: The unique ID of the video to retrieve.
    """
    try:
        video = client.video_manager.get_video(video_id)
        if video is None:
            raise HTTPException(status_code=404, detail=f"Video with id '{video_id}' not found.")
        return video
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")
    
    
##### PLAYLIST ENDPOINTS #####


@app.get("/api/playlists")
def list_playlists():
    """
    Retrieves a list of all playlists stored in the database.
    """
    try:
        return client.playlist_manager.list_playlists()
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.get("/api/playlists/{playlist_id}")
def get_playlist(playlist_id: str):
    """
    Retrieves detailed information for a specific playlist.

    - **playlist_id**: The unique ID of the playlist to retrieve.
    """
    try:
        playlist = client.playlist_manager.get_playlist(playlist_id)
        if playlist is None:
            raise HTTPException(status_code=404, detail=f"Playlist with id '{playlist_id}' not found.")
        return playlist
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.get("/api/playlists/{playlist_id}/videos")
def get_playlist_videos(playlist_id: str, limit: int = None, sort_by: str = "position"):
    """
    Retrieves a list of videos for a specific playlist.

    - **playlist_id**: The unique ID of the playlist.
    - **limit**: The maximum number of videos to return.
    - **sort_by**: The sorting criteria ('position', 'published_at', 'title').
    """
    try:
        return client.playlist_manager.get_playlist_videos(playlist_id, limit=limit, sort_by=sort_by)
    except ValueError as e:
        # Catches the "not found" error from the backend.
        raise HTTPException(status_code=404, detail=str(e))
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


@app.delete("/api/playlists/{playlist_id}", status_code=200)
def delete_playlist(playlist_id: str):
    """
    Deletes a specific playlist from the database.

    - **playlist_id**: The unique ID of the playlist to delete.
    """
    try:
        client.playlist_manager.delete_playlist(playlist_id)
        return {"message": f"Playlist with id '{playlist_id}' deleted successfully."}
    except ValueError as e:
        # Catches the "not found" error from the backend.
        raise HTTPException(status_code=404, detail=str(e))
    except sqlite3.Error as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")


# Root endpoint for basic connectivity check
@app.get("/")
def read_root():
    return {"message": "Welcome to the YouTube Channel Retriever API"}