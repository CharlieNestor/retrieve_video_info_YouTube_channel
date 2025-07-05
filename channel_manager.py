from datetime import datetime, timedelta
from storage import SQLiteStorage
from downloader import MediaDownloader
from datetime import datetime


class ChannelManager:

    def __init__(self, storage: SQLiteStorage, downloader: MediaDownloader, update_threshold_days: int = 7):
        """
        Initialize the ChannelManager with storage and downloader dependencies.
        The ChannelManager handles operations related to YouTube channels including
        fetching, storing, and updating channel information and their videos.
        
        :param storage: SQLiteStorage instance for data persistence operations
        :param downloader: MediaDownloader instance for fetching data from YouTube API
        :param update_threshold_days: The number of days after which channel data is considered stale.
        """
        self.storage = storage
        self.downloader = downloader
        self.update_threshold_days = update_threshold_days
        self.update_threshold_days = update_threshold_days

    
    def process(self, channel_id: str, force_update: bool = False) -> dict:
        """
        Process a channel: fetch info, store in database, return data
        
        :param channel_id: YouTube channel ID to process
        :param force_update: If True, force update regardless of last update time. Defaults to False.
        :return: dict: Channel information containing metadata
        """
        # First check if we already have this channel
        existing_channel = self.storage.get_channel(channel_id)
        if existing_channel:
            # Force update if requested OR if it needs an update based on time
            if force_update or self._needs_update(existing_channel):
                print(f"Updating channel {channel_id} ...")
                return self.update_channel(channel_id)
            # Otherwise, return the existing data
            print(f"Channel {channel_id} exists. Returning cached data.")
            return existing_channel

        # Fetch channel info from YouTube if it doesn't exist
        print(f"Channel {channel_id} not found in DB. Fetching...")
        try:
            channel_info = self.downloader.get_channel_info(channel_id)
            if not channel_info:
                raise ValueError(f"Could not fetch info for channel {channel_id}")
            
            # Store in database
            self.storage.save_channel(channel_info)
            print(f"Successfully fetched and saved channel {channel_id}.")
            return channel_info
            
        except Exception as e:
            print(f"Error processing channel {channel_id}: {str(e)}")
            raise

    def update_channel(self, channel_id: str) -> dict:
        """
        Update a channel's information with fresh data from YouTube.
        Fetches the latest channel data from YouTube API and updates the stored
        information in the database, replacing any existing data.
        
        :param channel_id: YouTube channel ID to update
        :return: dict: Updated channel information with latest metadata
        """
        try:
            # Get fresh channel data
            channel_info = self.downloader.get_channel_info(channel_id)
            if not channel_info:
                raise ValueError(f"Could not fetch updated info for channel {channel_id}")
            
            # Update in database (replaces existing)
            self.storage.save_channel(channel_info)
            
            # Update video list
            #self.sync_channel_videos(channel_id)    # TODO: Add and / or update videos (bulk operations)
            
            return channel_info
            
        except Exception as e:
            print(f"Error updating channel {channel_id}: {str(e)}")
            raise

    
    def _needs_update(self, existing_channel: dict) -> bool:
        """
        Determines if a channel needs updating based on its last update timestamp.
        
        :param existing_channel: Existing channel data from database
        :return: bool: True if channel needs update, False otherwise
        """
        if 'last_updated' not in existing_channel.keys() or not existing_channel['last_updated']:
            return True # Needs update if timestamp is missing
            
        # Convert string timestamp to datetime
        try:
            # SQLite CURRENT_TIMESTAMP format: "YYYY-MM-DD HH:MM:SS"
            # Parse the timestamp to datetime object
            last_updated_str = existing_channel['last_updated']
            
            # SQLite stores timestamps in "YYYY-MM-DD HH:MM:SS" format by default
            if ' ' in last_updated_str and ':' in last_updated_str:
                # Standard SQLite format from CURRENT_TIMESTAMP
                last_updated = datetime.strptime(last_updated_str, '%Y-%m-%d %H:%M:%S')
            elif 'T' in last_updated_str:  # ISO format with T separator
                if last_updated_str.endswith('Z'):
                    # ISO format with Z timezone indicator
                    last_updated_str = last_updated_str.replace('Z', '+00:00')
                last_updated = datetime.fromisoformat(last_updated_str)
            else:
                # Unexpected format - log and assume update is needed
                print(f"Unexpected timestamp format: {last_updated_str}")
                return True
            
            # Get current time
            now = datetime.now()

            # Calculate time difference
            time_difference = now - last_updated
            update_threshold_seconds = self.update_threshold_days * 24 * 60 * 60

            needs_update = time_difference.total_seconds() > update_threshold_seconds
            if needs_update:
                print(f"Channel {existing_channel.get('id')} needs update. Last updated: {last_updated_str} ({time_difference.days} days ago).")
            # else:
            #      print(f"Video {existing_video.get('id')} is up-to-date. Last updated: {last_updated_str} ({time_difference.days} days ago).")
            return needs_update
        except Exception as e:
            print(f"Error parsing timestamp: {str(e)}")
            # If we can't parse the timestamp, better to update
            return True
        
    
    def get_channel(self, channel_id: str) -> dict:
        """
        Retrieves a single channel's data from the database.

        :param channel_id: The YouTube channel ID.
        :return: A dictionary containing the channel's data, or None if not found.
        """
        return self.storage.get_channel(channel_id)

    def list_channels(self) -> list:
        """
        Retrieves a list of all channels from the database.

        :return: A list of channel dictionaries.
        """
        return self.storage.list_channels()

    def get_channel_videos(self, channel_id: str, limit: int = 100, sort_by: str = 'published_at') -> list:
        """
        Retrieve videos associated with a specific YouTube channel from the database.
        
        :param channel_id: YouTube channel ID
        :param limit: Maximum number of videos to return, defaults to 100
        :param sort_by: Field to sort videos by, defaults to 'published_at'
                        Valid values 'title', 'published_at'
        :return: list: List of video dictionaries containing video metadata,
                sorted by date (newest first) or empty list if none found
        """
        # Verify channel exists
        if not self.storage._channel_exists(channel_id):
            print(f"WARNING: Channel {channel_id} not found in database.")
            return []
        
        # Delegate the call to the storage layer.
        videos = self.storage.list_channel_videos(
            channel_id, 
            limit=limit, 
            sort_by=sort_by
        )

        if not videos:
            print(f"No videos found for channel {channel_id}")
            return []
        
        return videos
    
    # TODO: Add method to search videos by title, description, tags, etc.
    
    def delete_channel(self, channel_id: str) -> bool:
        """
        Deletes a channel and all its associated data (videos, playlists, tags, timestamps)
        from the database.

        :param channel_id: The ID of the channel to delete.
        :return: True if deletion was successful, False otherwise.
        """
        if not channel_id:
            print("ERROR: channel_id cannot be empty for deletion.")
            return False
        
        if not self.storage._channel_exists(channel_id):
            print(f"Channel {channel_id} not found in database. Nothing to delete.")
            return False
            
        try:
            # The cascade option in SQLiteStorage.delete_channel handles associated videos.
            # The schema's ON DELETE CASCADE handles playlists, video_tags, and timestamps.
            self.storage.delete_channel(channel_id, cascade=True)
            print(f"Successfully deleted channel {channel_id} and all its associated data.")
            return True
        except Exception as e:
            print(f"Error deleting channel {channel_id}: {str(e)}")
            return False

    
