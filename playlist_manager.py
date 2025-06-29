
from storage import SQLiteStorage
from downloader import MediaDownloader
from video_manager import VideoManager
from datetime import datetime
from typing import Dict, Any, Union, List

class PlaylistManager:

    def __init__(self, storage: SQLiteStorage, downloader: MediaDownloader, video_manager: VideoManager):
        """
        Initialize PlaylistManager.

        :param storage: SQLiteStorage instance for data persistence.
        :param downloader: MediaDownloader instance for fetching data.
        :param video_manager: VideoManager instance for processing videos within playlists.
        """
        self.storage = storage
        self.downloader = downloader
        self.video_manager = video_manager

    
    def process(self, playlist_id: str, force_update: bool = False, verbose: bool = False) -> Union[dict, None]:
        """
        Process a playlist: fetch info if needed, store in database, process its videos, and return data.
        Returns None if the playlist cannot be processed or found.

        :param playlist_id: YouTube playlist ID.
        :param force_update: If True, force update regardless of last update time. Defaults to False.
        :param verbose: If True, print detailed processing information. Defaults to False.
        :return: Playlist information dictionary or None.
        """
        try:
            existing_playlist = self.storage.get_playlist(playlist_id)
            if existing_playlist and not force_update and not self._needs_update(existing_playlist):
                print(f"Playlist {playlist_id} exists. Returning cached data.")
                return existing_playlist

            if existing_playlist and (force_update or self._needs_update(existing_playlist)):
                print(f"Updating playlist {playlist_id}...") 
                # Fall through to fetch and update logic
            elif not existing_playlist:
                print(f"Playlist {playlist_id} not found in DB. Fetching...")

            # Fetch playlist info from YouTube
            playlist_info = self.downloader.get_playlist_info(playlist_id)
            if not playlist_info:
                print(f"ERROR: Could not fetch info for playlist {playlist_id}")
                return None

            # Ensure the playlist's channel exists
            channel_id = playlist_info.get('channel_id')
            if channel_id and not self.storage.channel_exists(channel_id):
                print(f"WARNING: Channel {channel_id} for playlist {playlist_id} not found. Processing channel...")
                try:
                    # Minimal channel processing.
                    channel_data = self.downloader.get_channel_info(channel_id)
                    if channel_data:
                        self.storage.save_channel(channel_data)
                    else:
                        print(f"WARNING: Could not fetch channel {channel_id} for playlist {playlist_id}. Playlist may lack full context.")
                except Exception as e_ch:
                    print(f"Error fetching channel {channel_id} for playlist {playlist_id}: {e_ch}")
                    # Decide if playlist processing should fail if channel fetch fails. For now, continue.

            # Save the playlist's own metadata
            self.storage.save_playlist(playlist_info) # This saves playlist-level details
            print(f"Successfully saved/updated playlist metadata for {playlist_id}.")

            # Process and link videos within the playlist
            videos_in_playlist = playlist_info.get('videos', [])
            processed_video_count = 0
            linked_video_count = 0
            failed_video_count = 0
            total_videos = len(videos_in_playlist)

            if total_videos > 0:
                print(f"Starting processing videos from playlist {playlist_id}...")

                for i, video_entry in enumerate(videos_in_playlist, 1):
                    video_id = video_entry.get('id')
                    if not video_id:
                        continue

                    # Show progress for verbose output or long operations
                    if verbose and total_videos > 10:  # Only show progress for larger playlists
                        print(f"Processing video {i}/{total_videos}: {video_id}")
                    elif verbose:
                        print(f"Processing video: {video_id}")

                    try:
                        video_details = self.video_manager.process(video_id, force_update=force_update)

                        if video_details:
                            processed_video_count += 1
                            # Note: Video-playlist association is already handled by save_playlist()
                            linked_video_count +=1
                        else:
                            failed_video_count += 1
                            print(f"Failed to process video {video_id} from playlist {playlist_id}.")
                    
                    except Exception as e:
                        failed_video_count += 1
                        print(f"ERROR: Failed to process video {video_id} from playlist {playlist_id}: {str(e)}")
            
                # Summary output
                print(f"Playlist processing complete: {processed_video_count}/{total_videos} videos processed successfully")
                if failed_video_count > 0:
                    print(f"Warning: {failed_video_count} videos failed to process")
            else:
                print(f"No videos found in playlist {playlist_id}. Nothing to process.")

            # Update the video_count in the playlist record based on actual linked videos if desired,
            # or trust the count from playlist_info. For now, yt-dlp's count is saved.

            return self.storage.get_playlist(playlist_id) # Return data from DB

        except Exception as e:
            print(f"Error processing playlist {playlist_id}: {str(e)}")
            return None
        
    
    def _needs_update(self, existing_playlist: dict, days: int = 30) -> bool:
        """
        Determine if a playlist needs to be updated.
        Checks 'last_updated' (our DB timestamp) and 'modified_date' (from YouTube if available).

        :param existing_playlist: Existing playlist data from database (as dict).
        :param days: Number of days after which our DB record is considered stale for a general refresh.
        :return: bool: True if playlist needs update, False otherwise.
        """
        last_updated_str = existing_playlist.get('last_updated')
        #youtube_modified_date_str = existing_playlist.get('modified_date') # YYYYMMDD format

        if not last_updated_str:
            print(f"Playlist {existing_playlist.get('id')} missing 'last_updated' timestamp. Needs update.")
            return True

        try:
            # Check our internal last_updated timestamp
            # Assuming last_updated_str is in '%Y-%m-%d %H:%M:%S' format from SQLite
            last_updated_dt = datetime.strptime(last_updated_str, '%Y-%m-%d %H:%M:%S')
            if (datetime.now() - last_updated_dt).days > days:
                print(f"Playlist {existing_playlist.get('id')} DB record is older than {days} days. Needs update.")
                return True
            
            return False
        except Exception as e:
            print(f"Error parsing timestamp for playlist {existing_playlist.get('id')}: {str(e)}. Assuming update needed.")
            return True
        
    def get_playlist(self, playlist_id: str) -> Union[dict, None]:
        """
        Get playlist data from database.
        
        :param playlist_id: YouTube playlist ID
        :return: Playlist information dictionary or None if not found
        """
        if not playlist_id:
            print("ERROR: playlist_id cannot be empty.")
            return None
            
        try:
            playlist_data = self.storage.get_playlist(playlist_id)
            if not playlist_data:
                print(f"Playlist {playlist_id} not found in database.")
                return None
                
            return playlist_data
            
        except Exception as e:
            print(f"Error retrieving playlist {playlist_id}: {str(e)}")
            return None
        
        
    def get_playlist_videos(self, playlist_id: str, limit: int = None, sort_by: str = "position") -> List[dict]:
        """
        Get all videos in a playlist from database.
        
        :param playlist_id: YouTube playlist ID
        :param limit: Maximum number of videos to return
        :param sort_by: Sort videos by 'position', 'published_at', or 'title'
        :return: List of video dictionaries
        """
        if not playlist_id:
            print("ERROR: playlist_id cannot be empty.")
            return []
            
        try:
            videos = self.storage.get_playlist_videos(playlist_id, limit=limit, sort_by=sort_by)
            
            if not videos:
                print(f"No videos found for playlist {playlist_id}")
                return []
                
            return videos
            
        except Exception as e:
            print(f"Error retrieving videos for playlist {playlist_id}: {str(e)}")
            return []
        
    def delete_playlist(self, playlist_id: str) -> bool:
        """
        Delete playlist from database.
        NOTE: This only removes the playlist metadata and associations, not the individual video records.
        
        :param playlist_id: YouTube playlist ID to delete
        :return: True if deletion was successful, False otherwise
        """
        if not playlist_id:
            print("ERROR: playlist_id cannot be empty for deletion.")
            return False
            
        # Check if playlist exists
        existing_playlist = self.get_playlist(playlist_id)
        if not existing_playlist:
            print(f"Playlist {playlist_id} not found in database. Nothing to delete.")
            return False
            
        try:
            # Note: Assuming storage has a delete_playlist method
            # This should be implemented in storage.py similar to delete_channel
            success = self.storage.delete_playlist(playlist_id)
            print(f"Successfully deleted playlist {playlist_id}")
            return success
            
        except Exception as e:
            print(f"Error deleting playlist {playlist_id}: {str(e)}")
            return False
