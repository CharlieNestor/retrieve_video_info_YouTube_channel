import sqlite3
import requests
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
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
    This helps to avoid client-side rate-limiting issues.
    """
    try:
        # Make a streaming request to the external URL
        response = requests.get(url, stream=True)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)

        # Get the content type from the original response
        media_type = response.headers.get('content-type')

        # Stream the content back to the client
        return StreamingResponse(response.iter_content(chunk_size=8192), media_type=media_type)

    except requests.exceptions.RequestException as e:
        # Handle exceptions from the requests library (e.g., connection errors, timeouts)
        raise HTTPException(status_code=502, detail=f"Failed to fetch image from external source: {e}")


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