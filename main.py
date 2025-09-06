import sqlite3
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
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

# Instantiate the YouTubeClient
# This single client instance will be shared across all API requests.
client = YouTubeClient()


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




# Root endpoint for basic connectivity check
@app.get("/")
def read_root():
    return {"message": "Welcome to the YouTube Channel Retriever API"}