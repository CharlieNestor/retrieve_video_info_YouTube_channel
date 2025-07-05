import os
from datetime import datetime, timedelta
from storage import SQLiteStorage
from downloader import MediaDownloader
from channel_manager import ChannelManager


class VideoManager:
    def __init__(self, storage: SQLiteStorage, downloader: MediaDownloader, update_threshold_days: int = 30):
        """
        Initialize VideoManager
        
        :param storage: SQLiteStorage instance for data persistence
        :param downloader: MediaDownloader instance for fetching data
        :param update_threshold_days: The number of days after which video data is considered stale.
        """
        self.storage = storage
        self.downloader = downloader
        self.update_threshold_days = update_threshold_days

    def _needs_update(self, existing_video: dict) -> bool:
        """
        Determines if a video needs updating based on its last update timestamp.
        
        :param existing_video: Existing video data from database
        :return: bool: True if video needs update, False otherwise
        """
        if 'last_updated' not in existing_video.keys() or not existing_video['last_updated']:
            return True # Needs update if timestamp is missing
            
        # Convert string timestamp to datetime
        try:
            # SQLite CURRENT_TIMESTAMP format: "YYYY-MM-DD HH:MM:SS"
            # Parse the timestamp to datetime object
            last_updated_str = existing_video['last_updated']
            
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
                print(f"Video {existing_video.get('id')} needs update. Last updated: {last_updated_str} ({time_difference.days} days ago).")
            return needs_update
        except Exception as e:
            print(f"Error parsing timestamp: {str(e)}")
            # If we can't parse the timestamp, better to update
            return True

    
    def process(self, video_id: str, force_update: bool = False) -> dict:
        """
        Process a video: fetch info if needed, store in database, return data.
        Returns None if the video cannot be processed or found.
        
        :param video_id: YouTube video ID
        :param force_update: If True, force update regardless of last update time. Defaults to False.
        :return: dict: Video information or None
        """
        if not isinstance(video_id, str):
            raise ValueError("video_id must be a string")

        try:
            existing_video = self.storage.get_video(video_id)
            if existing_video:
                # Force update if requested OR if it needs an update based on time
                if force_update or self._needs_update(existing_video):
                    print(f"Updating video {video_id} ...")
                    return self.update_video(video_id)
                # Otherwise, return the existing data
                print(f"Video {video_id} exists. Returning cached data.")
                return existing_video

            # Video doesn't exist in DB, fetch it
            print(f"Video {video_id} not found in DB. Fetching...")
            video_info = self.downloader.get_video_info(video_id)
            if not video_info:
                print(f"Could not fetch info for video {video_id}")
                return None # Indicate failure to fetch

            # Ensure the channel exists before saving the video
            channel_id = video_info.get('channel_id')
            if channel_id and not self.storage._channel_exists(channel_id):
                print(f"WARNING: Channel {channel_id} for video {video_id} not found in DB. Fetching channel info...")
                # Attempt to fetch and save the channel minimally
                try:
                    channel_info = self.downloader.get_channel_info(channel_id)
                    if channel_info:
                        self.storage.save_channel(channel_info)
                    else:
                        print(f"WARNING: Could not fetch info for channel {channel_id}. Video {video_id} might lack channel context.")
                        return None
                except Exception as e:
                     print(f"Error fetching channel {channel_id} for video {video_id}: {e}")
                     return None
            
            # --- Save Core Video Data ---
            self.storage.save_video(video_info)

            # --- Save Tags ---
            tags_to_save = video_info.get('tags', [])
            self.storage.save_video_tags(video_id, tags_to_save)
            
             # --- Fetch and Save Timestamps ---
            video_timestamps = self.downloader.get_video_timestamps(video_id)
            self.storage.save_video_timestamps(video_id, video_timestamps)

            print(f"Successfully fetched and saved video {video_id} and its associations.")
            return video_info

        except Exception as e:
            print(f"Error processing video {video_id}: {str(e)}")
            # Potentially re-raise or handle specific exceptions
            return None # Indicate failure
        
    def update_video(self, video_id: str) -> dict:
        """
        Fetches fresh video information and updates the database.

        :param video_id: YouTube video ID
        :return: updated video Info or None on failure
        """
        try:
            # Get fresh video data
            video_info = self.downloader.get_video_info(video_id)
            if not video_info:
                print(f"WARNING: Failed to fetch updated info for video {video_id}, downloader returned None.")
                # Update status to indicate fetch failure during update
                self.storage._update_video_status(video_id, 'unavailable')
                return None

            # Ensure channel exists (minimal check/fetch, don't force update channel)
            channel_id = video_info.get('channel_id')
            if channel_id and not self.storage.channel_exists(channel_id):
                print(f"Warning: Channel {channel_id} for video {video_id} not found during update. Fetching channel info...")
                try:
                    channel_manager = ChannelManager(self.storage, self.downloader)
                    channel_manager.process(channel_id, force_update=False) # Don't force channel update
                except Exception as e:
                    print(f"Error fetching/processing channel {channel_id} during video update: {e}")
                    # If the channel cannot be fetched we won't update the video
                    return None

            # --- Save Core Video Data ---
            self.storage.save_video(video_info)

            # --- Save Tags ---
            tags_to_save = video_info.get('tags', [])
            self.storage.save_video_tags(video_id, tags_to_save)
            
            # --- Fetch and Save Timestamps (Update) ---
            video_timestamps = self.downloader.get_video_timestamps(video_id)
            self.storage.save_video_timestamps(video_id, video_timestamps)

            print(f"Successfully updated video {video_id} in database.")
            return video_info

        except Exception as e:
            print(f"Error updating video {video_id}: {str(e)}")
            self.storage._update_video_status(video_id, 'update_error')
            return None
        
    def get_video(self, video_id: str) -> dict:
        """
        Retrieves a single video's data from the database.

        :param video_id: The YouTube video ID.
        :return: A dictionary containing the video's data, or None if not found.
        """
        return self.storage.get_video(video_id)

    def list_channel_videos(self, channel_id: str) -> list:
        """
        Retrieves a list of all videos for a specific channel from the database.

        :param channel_id: The YouTube channel ID.
        :return: A list of video dictionaries.
        """
        return self.storage.list_channel_videos(channel_id)

    def download_video(self, video_id: str, force_download: bool=False) -> str:
            """
            Downloads a video file, updates its status in the database, 
            and returns the file path. This method orchestrates the download process by:
            1. Ensuring the video exists in the database (processing if needed).
            2. Verifying if the video has already been downloaded (unless forced).
            3. Retrieving necessary channel information for creating the correct folder structure.
            4. Calling the downloader to perform the download.
            5. Updating the database with the new file path upon success.
    
            :param video_id: The unique ID of the video to download.
            :param force_download: If True, forces the download even if the video is already downloaded.
            :return: The absolute path to the downloaded file if successful, otherwise None.
            """
            # 1. Ensure video exists in database (process if needed)
            video_info = self.storage.get_video(video_id)
            if not video_info:
                print(f"Video {video_id} not found in database. Processing first...")
                video_info = self.process(video_id)
                if not video_info:
                    print(f"ERROR: Could not process video {video_id}. Cannot download.")
                    return None
    
            # 2. Check if the video is already downloaded (unless forced)
            if not force_download and video_info.get('file_path') and os.path.exists(video_info['file_path']):
                print(f"INFO: Video {video_id} is already downloaded at: {video_info['file_path']}")
                return video_info['file_path']
    
            # 3. Get channel info needed for the download path
            channel_id = video_info.get('channel_id')
            if not channel_id:
                print(f"ERROR: Video {video_id} is missing a channel_id in the database.")
                return None
    
            channel_info = self.storage.get_channel(channel_id)
            if not channel_info:
                print(f"ERROR: Channel {channel_id} for video {video_id} not found in the database.")
                return None
    
            # 4. Call the downloader to perform the actual download
            print(f"Starting download for video: {video_id}")
            try:
                file_path = self.downloader.download_video(
                    video_id=video_id,
                    channel_id=channel_id,
                    channel_name=channel_info.get('name', 'Unknown Channel')
                )

                # 5. Update the database if the download was successful
                if file_path and os.path.exists(file_path):
                    self.storage._update_video_download_status(video_id, file_path)
                    print(f"SUCCESS: Video {video_id} downloaded to {file_path} and database updated.")
                    return file_path
                else:
                    print(f"FAILURE: The download process for video {video_id} did not return a valid file path.")
                    #self.storage._update_video_status(video_id, 'download_failed')
                    return None
                    
            except Exception as e:
                print(f"ERROR: Download failed for video {video_id}: {e}")
                #self.storage._update_video_status(video_id, 'download_failed')
                return None