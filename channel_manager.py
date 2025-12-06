from datetime import datetime, timedelta
import os
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
        # Verify channel exists first, and raise an error if it does not.
        if not self.get_channel(channel_id):
            raise ValueError(f"Channel with id '{channel_id}' not found.")
        
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
    
    def get_channel_playlists(self, channel_id: str, limit: int = None, sort_by: str = "title") -> list:
        """
        Retrieves a list of all playlists for a channel from the database.

        :param channel_id: The YouTube channel ID.
        :param limit: Optional. The maximum number of playlists to return.
        :param sort_by: The column to sort by. Valid values are 'title', 'video_count'.
        :return: A list of dictionaries, each containing playlist 'id' and 'title'.
        """
        if not channel_id:
            # Raising ValueError here to be caught by the API layer for a 422 or 400 response.
            raise ValueError("Channel ID cannot be empty.")
        
        # Let exceptions from the storage layer (e.g., ValueError for not found, sqlite3.Error) propagate.
        return self.storage.list_playlists(
            channel_id=channel_id,
            limit=limit,
            sort_by=sort_by
        )
    
    def get_online_video_list(self, channel_id: str) -> list:
        """
        Fetches a list of all videos for a channel directly from YouTube.

        This method provides a way to see all available videos on the channel's
        page, regardless of whether they are stored in the local database.

        :param channel_id: The YouTube channel ID.
        :return: A list of dictionaries, each containing video 'id' and 'title'.
        """
        if not channel_id:
            print("ERROR: channel_id cannot be empty.")
            return []
        
        try:
            return self.downloader.get_channel_video_list(channel_id)
        except Exception as e:
            print(f"Error fetching online video list for channel {channel_id}: {str(e)}")
            return []

    def get_channel_tags(self, channel_id: str, limit: int = None, min_video_count: int = 1) -> list:
        """
        Retrieves unique tags for a channel from the local database.

        This method aggregates all unique tags from the videos of a specific
        channel that have been saved locally. It can also count how many
        videos are associated with each tag.

        :param channel_id: The ID of the channel.
        :param limit: Optional. The maximum number of unique tags to return.
        :param min_video_count: The minimum number of videos a tag must be
                                associated with to be included.
        :return: A list of dictionaries, each with 'tag_name' and 'video_count'.
        """
        if not channel_id:
            raise ValueError("Channel ID cannot be empty.")
            
        return self.storage.get_tags_channel(
            channel_id, 
            limit=limit, 
            min_video_count=min_video_count
        )

    def get_video_download_states(self, channel_id: str) -> dict:
        """
        Categorizes videos for a channel into downloaded and not downloaded lists.

        This method efficiently queries the database to get the download status
        for all videos of a given channel and returns them in a structured format.

        :param channel_id: The YouTube channel ID.
        :return: A dictionary with two keys, 'downloaded' and 'not_downloaded',
                 each containing a list of video dictionaries ('id', 'title').
        """
        if not channel_id:
            print("ERROR: channel_id cannot be empty.")
            return {"downloaded": [], "not_downloaded": []}

        try:
            all_videos = self.storage.get_videos_with_download_status(channel_id)
            
            downloaded_videos = []
            not_downloaded_videos = []

            for video in all_videos:
                video_info = {'id': video['id'], 'title': video['title']}
                if video['downloaded'] == 1:
                    downloaded_videos.append(video_info)
                else:
                    not_downloaded_videos.append(video_info)
            
            return {
                "downloaded": downloaded_videos,
                "not_downloaded": not_downloaded_videos
            }

        except Exception as e:
            print(f"Error getting video download states for channel {channel_id}: {str(e)}")
            return {"downloaded": [], "not_downloaded": []}
    
    # TODO: Add method to search videos by title, description, tags, etc.
    
    def delete_channel(self, channel_id: str):
        """
        Deletes a channel and all its associated data from the database and local storage.
        
        This process follows a strict "Check then Act" pattern:
        1. VERIFICATION PHASE (Blocking):
           - Checks consistency for ALL videos in the channel.
           - If a video is marked as 'downloaded', it MUST have a valid 'file_path'.
           - The file at 'file_path' MUST exist on the filesystem.
           - If ANY inconsistency is found (e.g., missing file, missing path), the process ABORTS
             with a ValueError, and NOTHING is deleted.
        
        2. EXECUTION PHASE (Destructive):
           - Deletes the confirmed video files from disk.
           - Deletes the channel directory (cleaning up any extra files like thumbnails/metadata).
           - Removes the channel and its metadata from the database (cascading to videos).
        
        :param channel_id: The ID of the channel to delete.
        :raises ValueError: If channel not found or ANY file inconsistency is detected.
        :raises sqlite3.Error: For underlying database errors.
        """
        if not channel_id:
            raise ValueError("Channel ID cannot be empty for deletion.")

        # --- 1. Get channel info ---
        channel_info = self.storage.get_channel(channel_id)
        if not channel_info:
            raise ValueError(f"Channel with ID {channel_id} does not exist.")

        # --- 2. VERIFICATION PHASE ---
        print(f"Verifying consistency for channel {channel_id} deletion...")
        videos_with_status = self.storage.get_videos_with_download_status(channel_id)
        
        videos_to_delete_files = []

        for v_status in videos_with_status:
            if v_status.get('downloaded') == 1:
                # Need full info to get file_path
                full_video = self.storage.get_video(v_status['id'])
                if not full_video:
                     raise ValueError(f"CRITICAL: Video {v_status['id']} found in list but missing in detail fetch.")
                
                file_path = full_video.get('file_path')
                
                # Check 1: Flag is 1, so file_path MUST be present
                if not file_path:
                    raise ValueError(f"ABORTING DELETION: Inconsistency detected for video {full_video['id']}. Marked as downloaded but 'file_path' is missing.")
                
                # Check 2: File at file_path MUST exist
                if not os.path.exists(file_path):
                     raise ValueError(f"ABORTING DELETION: Inconsistency detected for video {full_video['id']}. marked as downloaded, but file not found at: {file_path}")
                
                videos_to_delete_files.append(file_path)

        # Confirm channel folder existence if we have files (sanity check)
        channel_dir = self.downloader.get_channel_dir(channel_info['name'], channel_id)
        if videos_to_delete_files and not os.path.exists(channel_dir):
             raise ValueError(f"ABORTING DELETION: Channel contains {len(videos_to_delete_files)} downloaded videos, but channel directory not found at: {channel_dir}")

        
        # --- 3. EXECUTION PHASE ---
        print("Verification successful. Proceeding with deletion.")
        
        # A. Delete individual video files
        import shutil
        for file_path in videos_to_delete_files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    print(f"Deleted file: {file_path}")
            except OSError as e:
                raise ValueError(f"Failed to delete file {file_path}: {e}. Aborting remainder of deletion.")

        # B. Delete the channel directory (recursively removes leftovers)
        if os.path.exists(channel_dir):
            try:
                shutil.rmtree(channel_dir)
                print(f"Deleted channel directory: {channel_dir}")
            except OSError as e:
                 raise ValueError(f"Failed to delete channel directory {channel_dir}: {e}")
        
        # C. Delete from DB
        self.storage.delete_channel(channel_id)
        print(f"Successfully deleted channel {channel_id} and all its associated data.")

    
