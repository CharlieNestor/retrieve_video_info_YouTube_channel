import os
from datetime import datetime, timedelta
from storage import SQLiteStorage
from downloader import MediaDownloader
from channel_manager import ChannelManager
from transcript_parser import TranscriptParser
from utils import compute_vtt_hash
from typing import Union


class VideoManager:
    def __init__(self, storage: SQLiteStorage, downloader: MediaDownloader, channel_manager: ChannelManager, update_threshold_days: int = 30):
        """
        Initialize VideoManager
        
        :param storage: SQLiteStorage instance for data persistence
        :param downloader: MediaDownloader instance for fetching data
        :param channel_manager: ChannelManager instance for handling channel-related operations.
        :param update_threshold_days: The number of days after which video data is considered stale.
        """
        self.storage = storage
        self.downloader = downloader
        self.channel_manager = channel_manager
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

    
    def process(self, video_id: str, force_update: bool = False, expected_channel_id: str = None) -> dict:
        """
        Process a video: fetch info, store in database, return data.
        If an expected_channel_id is provided, the video will be skipped if
        it does not belong to that channel.

        :param video_id: YouTube video ID to process.
        :param force_update: If True, force update regardless of last update time. Defaults to False.
        :param expected_channel_id: Optional. If provided, ensures the video belongs to this channel.
        :return: Dictionary with video information or None if skipped or failed.
        """
        # If an expected channel is provided, we must validate ownership before proceeding.
        if expected_channel_id:
            # To validate, we need the video's actual channel ID. We must fetch it from the downloader.
            video_info_for_check = self.downloader.get_video_info(video_id)
            if not video_info_for_check:
                print(f"Could not fetch info for video {video_id} to validate channel ownership.")
                return None # Cannot proceed without video info

            actual_channel_id = video_info_for_check.get('channel_id')
            if actual_channel_id != expected_channel_id:
                print(f"WARNING: Skipping video {video_id}. It belongs to channel '{actual_channel_id}' but was expected in playlist from channel '{expected_channel_id}'.")
                return None

        # Check if we need to update
        existing_video = self.storage.get_video(video_id)
        if existing_video:
            if force_update or self._needs_update(existing_video):
                print(f"Updating video {video_id}...")
                return self.update_video(video_id)

            # If video exists and is up-to-date, check if transcript is missing
            if not self.storage.get_transcript(video_id):
                print(f"Video {video_id} is up-to-date, but transcript is missing. Fetching transcript...")
                try:
                    tr = self.downloader.get_raw_video_transcript(video_id)
                    if tr and tr.get('vtt'):
                        vtt = tr['vtt']
                        lang = tr.get('lang') or 'unknown'
                        source = tr.get('source')
                        is_translation = bool(tr.get('is_translation'))
                        # Compute hash using centralized utility for consistency
                        vtt_hash = compute_vtt_hash(vtt)

                        plain_text = TranscriptParser(vtt).get_plain_text()
                        self.storage.save_transcript(
                            video_id=video_id,
                            vtt=vtt,
                            plain_text=plain_text,
                            lang=lang,
                            source=source,
                            is_translation=is_translation,
                            vtt_hash=vtt_hash
                        )
                        print(f"Successfully backfilled transcript for video {video_id}.")
                except Exception as e:
                    print(f"Warning: failed to backfill transcript for {video_id}: {e}")

            print(f"Video {video_id} exists. Returning cached data.")
            return existing_video

        # Video doesn't exist in DB, fetch it
        print(f"Video {video_id} not found in DB. Fetching...")
        video_info = self.downloader.get_video_info(video_id)
        if not video_info:
            print(f"Could not fetch info for video {video_id}")
            return None

        # If channel doesn't exist, fetch and save it
        channel_id = video_info.get('channel_id')
        if channel_id and not self.channel_manager.get_channel(channel_id):
            print(f"WARNING: Channel {channel_id} for video {video_id} not found in DB. Fetching channel info...")
            self.channel_manager.process(channel_id)

        # --- Save Core Video Data ---
        self.storage.save_video(video_info)

        # --- Save Tags ---
        tags_to_save = video_info.get('tags', [])
        self.storage.save_video_tags(video_id, tags_to_save)

        # --- Fetch and Save Timestamps ---
        video_timestamps = self.downloader.get_video_timestamps(video_id)
        self.storage.save_video_timestamps(video_id, video_timestamps)

        # --- Fetch and Save Transcript (VTT + plain text) ---
        try:
            tr = self.downloader.get_raw_video_transcript(video_id)
            if tr and tr.get('vtt'):
                vtt = tr['vtt']
                lang = tr.get('lang') or 'unknown'
                source = tr.get('source')
                is_translation = bool(tr.get('is_translation'))
                # Compute hash using centralized utility for consistency
                vtt_hash = compute_vtt_hash(vtt)

                plain_text = TranscriptParser(vtt).get_plain_text()
                self.storage.save_transcript(
                    video_id=video_id,
                    vtt=vtt,
                    plain_text=plain_text,
                    lang=lang,
                    source=source,
                    is_translation=is_translation,
                    vtt_hash=vtt_hash
                )
        except Exception as e:
            print(f"Warning: failed to fetch/save transcript for {video_id}: {e}")

        print(f"Successfully fetched and saved video {video_id} and its associations.")
        return video_info
        
    def update_video(self, video_id: str) -> dict:
        """
        Fetches fresh video data, compares it with existing data, and performs
        an update only if changes are detected. The update is atomic.
        If no changes are found, it just updates the 'last_updated' timestamp.

        :param video_id: YouTube video ID
        :return: updated video Info or None on failure
        """
        try:
            # --- 1. Fetch new data and old data ---
            new_video_info = self.downloader.get_video_info(video_id)
            if not new_video_info:
                print(f"WARNING: Failed to fetch updated info for video {video_id}, downloader returned None.")
                self.storage._update_video_status(video_id, 'unavailable')
                return None

            old_video = self.storage.get_video(video_id)
            if not old_video:
                # This case should ideally not be hit if called from process(), but as a safeguard:
                print(f"ERROR: Cannot update video {video_id} as it does not exist in the database.")
                return None
            
            old_transcript = self.storage.get_transcript(video_id)

            # --- 2. Compare and decide what to update ---
            changes = {}
            
            # Data to pass to transactional update, initialized to None
            data_to_update = {
                'video_info': None,
                'tags': None,
                'timestamps': None,
                'transcript_data': None
            }

            # Compare core info fields
            core_fields_to_check = ['title', 'description', 'view_count', 'like_count', 'duration']
            for field in core_fields_to_check:
                if old_video.get(field) != new_video_info.get(field):
                    changes['video_info'] = True
                    data_to_update['video_info'] = new_video_info
                    break
            
            # Compare tags (normalized, case-insensitive, trimmed)
            new_tags = set(t.strip().lower() for t in new_video_info.get('tags', []) if isinstance(t, str) and t.strip())
            old_tags = set(t.strip().lower() for t in old_video.get('tags', []) if isinstance(t, str) and t.strip())
            if new_tags != old_tags:
                changes['tags'] = True
                data_to_update['tags'] = sorted(list(new_tags)) # Save normalized list

            # Compare timestamps
            new_timestamps = self.downloader.get_video_timestamps(video_id) or []
            # Convert lists of dicts to something hashable for comparison, like a tuple of tuples
            old_ts_comparable = tuple(sorted((d['time_seconds'], d['description']) for d in old_video.get('timestamps', [])))
            new_ts_comparable = tuple(sorted((d['start_time'], d['title']) for d in new_timestamps))
            if old_ts_comparable != new_ts_comparable:
                changes['timestamps'] = True
                data_to_update['timestamps'] = new_timestamps

            # Compare transcript using hash
            new_tr_raw = self.downloader.get_raw_video_transcript(video_id)
            new_tr_data_for_save = None
            new_vtt_hash = None

            if new_tr_raw and new_tr_raw.get('vtt'):
                # Compute hash using centralized utility for consistency
                new_vtt_hash = compute_vtt_hash(new_tr_raw['vtt'])
                
                if not old_transcript or old_transcript.get('vtt_hash') != new_vtt_hash:
                    changes['transcript'] = True
                    plain_text = TranscriptParser(new_tr_raw['vtt']).get_plain_text()
                    new_tr_data_for_save = {
                        'vtt': new_tr_raw['vtt'], 'plain_text': plain_text,
                        'lang': new_tr_raw.get('lang') or 'unknown', 'source': new_tr_raw.get('source'),
                        'is_translation': bool(new_tr_raw.get('is_translation')), 'vtt_hash': new_vtt_hash
                    }
            # If no new transcript is available, keep the existing transcript unchanged (no-op)

            if changes.get('transcript'):
                data_to_update['transcript_data'] = new_tr_data_for_save


            # --- 3. Execute update if changes were detected ---
            if not changes:
                print(f"No data changes detected for video {video_id}. Refreshing timestamp.")
                self.storage.touch_video_timestamp(video_id)
            else:
                print(f"Changes detected for video {video_id} in: {list(changes.keys())}. Performing transactional update.")
                
                # Ensure channel exists before transaction
                channel_id = new_video_info.get('channel_id')
                if channel_id and not self.channel_manager.get_channel(channel_id):
                    self.channel_manager.process(channel_id, force_update=False)

                self.storage.save_video_update_transactional(
                    video_id=video_id,
                    video_info=data_to_update['video_info'],
                    tags=data_to_update['tags'],
                    timestamps=data_to_update['timestamps'],
                    transcript_data=data_to_update['transcript_data']
                )
                print(f"Successfully updated video {video_id} in database.")

            return self.storage.get_video(video_id) # Return the fresh data from DB

        except Exception as e:
            print(f"Error updating video {video_id}: {str(e)}")
            try:
                self.storage._update_video_status(video_id, 'update_error')
            except Exception as status_e:
                print(f"Failed to update video status to 'update_error' for {video_id}: {status_e}")
            return None

    def get_transcript_plain(self, video_id: str, lang: str = None) -> Union[str, None]:
        tr = self.storage.get_transcript(video_id, lang)
        return tr.get('plain_text') if tr else None

    def get_transcript_by_chapters(self, video_id: str, lang: str = None) -> list:
        # Compute on read (don’t store segments)
        tr = self.storage.get_transcript(video_id, lang)
        if not tr or not tr.get('vtt'):
            return []
        timestamps = self.storage.get_video_timestamps(video_id) or []
        # duration is optional here; pass 0 if unknown
        video = self.storage.get_video(video_id) or {}
        duration = int(video.get('duration') or 0)
        return TranscriptParser(tr['vtt']).segment_by_chapters(timestamps, duration)
        
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

    def list_all_videos(self) -> list:
        """
        Retrieves a list of all videos from the database.

        :return: A list of video dictionaries.
        """
        return self.storage.list_all_videos()

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