import os
import re
import time
import yt_dlp
import requests
from datetime import datetime
from typing import Dict, Any, Union, List
from utils import format_datetime, sanitize_filename



class MediaDownloader:


    def __init__(self, download_dir: str = None):
        """
        Initialize MediaDownloader
        
        :param download_dir: Directory where videos will be downloaded.
                            If None, uses the system's Downloads folder.
        """
        self.download_dir = os.path.abspath(download_dir)
        self._filename_sanitizer = None # Temporary storage for hook result
        
        # Common yt-dlp options
        self.common_options = {
            'quiet': True,
            'no_warnings': True,    # Suppress warnings
            'extract_flat': True,   # Do not download video by default
            #'verbose':True,
        }


    ##### RETRIEVE INFO METHODS #####


    def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """
        Get comprehensive YouTube channel information with adaptive data extraction.
    
        This method handles various response structures returned by yt-dlp when extracting
        YouTube channel data. Different response formats occur depending on how the channel
        organizes content and how yt-dlp represents this data:
        
        1. Flat Structure (≥10 entries): yt-dlp returns each video as a separate entry
        in the 'entries' list. Common for standard channel views.
        
        2. Nested Structure: yt-dlp returns category containers instead of direct videos:
        a) Each entry represents a content category (Videos/Shorts/Live)
        b) Each category contains a 'playlist_count' indicating the number of videos
        This typically happens when a channel has content organized into tabs.
        
        3. Small Flat Structure: For channels with few videos (<10), yt-dlp may still
        return direct video entries rather than categories.
        
        4. Empty Channel: Handles channels with no content where yt-dlp returns
        empty 'entries' list.
        
        :param channel_id: YouTube channel ID
        :return: Dictionary containing channel metadata:
            - id: Channel identifier
            - name: Channel title
            - description: Channel description
            - subscriber_count: Number of subscribers
            - video_count: Total videos across all categories
            - content_breakdown: Dict mapping content types to video counts
            - thumbnail_url: Dict with profile picture and banner URLs
        """
        # Validate channel_id
        if not isinstance(channel_id, str):
            raise ValueError("Channel ID must be a string")

        url = f"https://www.youtube.com/channel/{channel_id}"
        options = {
            **self.common_options,
            'extract_flat': True,   # Do not download videos, just extract info
        }

        MIN_ENTRIES_FOR_FLAT_ASSUMPTION = 10 # Threshold
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Handle CHANNEL THUMBNAILS
                # Get just the original profile picture and banner
                thumbnails = {
                    'profile_picture': None,    # Original avatar
                    'banner': None              # Original banner
                }
                
                if 'thumbnails' in info:
                    for thumb in info['thumbnails']:
                        thumb_id = thumb.get('id', '')
                        if 'avatar_uncropped' in thumb_id:
                            thumbnails['profile_picture'] = thumb['url']
                        elif 'banner_uncropped' in thumb_id:
                            thumbnails['banner'] = thumb['url']

                # Handle CHANNEL N_VIDEOS
                # Calculate total videos by summing up all content types
                total_videos = 0
                content_counts = {}
                
                if 'entries' in info and info['entries']:
                    entries = info['entries']
                    num_entries = len(entries)
                    first_entry = entries[0] # Need to check this

                    if num_entries >= MIN_ENTRIES_FOR_FLAT_ASSUMPTION:
                        # Case 1: High count -> Assume Flat Video Structure
                        # print(f"DEBUG: Assuming flat structure (>= {MIN_ENTRIES_FOR_FLAT_ASSUMPTION} entries) for {channel_id}")
                        total_videos = num_entries
                        content_counts['Videos'] = num_entries
                    else:
                        # Case 2: Low count -> Check first entry's structure
                        # Heuristic: Does it look like a category playlist?
                        is_nested_structure = 'playlist_count' in first_entry or \
                                            any(cat in first_entry.get('title', '') for cat in ['Videos', 'Shorts', 'Live'])

                        if is_nested_structure:
                            # Case 2a: Nested Structure (Categories)
                            # print(f"DEBUG: Assuming nested structure (< {MIN_ENTRIES_FOR_FLAT_ASSUMPTION} entries, looks like category) for {channel_id}")
                            for content_type in entries:
                                count = content_type.get('playlist_count', 0)
                                title = content_type.get('title', 'Unknown Category')
                                
                                # Standardize category keys
                                category_key = 'Unknown'
                                if 'Videos' in title: category_key = 'Videos'
                                elif 'Shorts' in title: category_key = 'Shorts'
                                elif 'Live' in title: category_key = 'Live'
                                
                                content_counts[category_key] = content_counts.get(category_key, 0) + count
                                total_videos += count
                        else:
                            # Case 2b: Flat Structure (Few Videos)
                            # print(f"DEBUG: Assuming flat structure (< {MIN_ENTRIES_FOR_FLAT_ASSUMPTION} entries, looks like video) for {channel_id}")
                            total_videos = num_entries
                            # Assign to 'Videos' category by default for flat structure
                            content_counts['Videos'] = num_entries 
                else:
                    # Case 4: No 'entries' and no 'video_count' -> Assume 0
                    print(f"Warning: Channel {channel_id} has no entries. Assuming 0 videos.")
                    total_videos = 0
                    content_counts['Unknown'] = 0

                return {
                    'id': channel_id,
                    'name': info.get('channel', None) or info.get('title', None),
                    'description': info.get('description'),
                    'subscriber_count': info.get('channel_follower_count'),
                    'video_count': total_videos,
                    'content_breakdown': content_counts,
                    'thumbnail_url': thumbnails
                }
                
        except Exception as e:
            print(f"Error fetching channel info: {str(e)}")
            raise

    def get_channel_video_list(self, channel_id: str) -> List[Dict[str, Any]]:
        """
        Efficiently retrieves a list of all videos, shorts, and live streams for a given channel.

        Uses yt-dlp's flat extraction to get a lightweight list of video
        titles and IDs without fetching full metadata for each video. It queries
        the 'Videos', 'Shorts', and 'Live' tabs of the channel page to ensure
        all content is discovered.

        :param channel_id: The YouTube channel ID.
        :return: A list of dictionaries, each containing 'id' and 'title'.
        """
        all_videos = {} # Use a dict to automatically handle duplicates by video ID

        # Always check the standard tabs for videos, shorts, and streams.
        content_tabs = ['videos', 'shorts', 'streams']

        options = {
            **self.common_options,
            'extract_flat': 'in_playlist',
        }

        with yt_dlp.YoutubeDL(options) as ydl:
            for tab in content_tabs:
                url = f"https://www.youtube.com/channel/{channel_id}/{tab}"
                try:
                    info = ydl.extract_info(url, download=False)
                    if 'entries' in info and info['entries']:
                        for entry in info['entries']:
                            if entry and entry.get('id'):
                                # Use video ID as key to prevent duplicates
                                all_videos[entry['id']] = {
                                    'id': entry.get('id'),
                                    'title': entry.get('title'),
                                }
                except yt_dlp.utils.DownloadError as e:
                    # It's expected that a channel may not have a 'streams' or other tabs.
                    # We can safely ignore these specific errors and continue.
                    error_str = str(e).lower()
                    if 'no videos found in this tab' in error_str or 'the channel is not currently live' in error_str:
                        pass  # Silently ignore expected errors.
                    else:
                        # For any other download error, we should still print a warning.
                        print(f"Warning: yt-dlp error on tab '{tab}' for channel {channel_id}: {e}")
                except Exception as e:
                    print(f"Error fetching channel video list for tab '{tab}' on channel {channel_id}: {e}")

        return list(all_videos.values())

    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """
        Extract detailed YouTube video metadata using yt-dlp.
        Gets title, channel info, metrics (views/likes), publication data,
        and content classification (short/live).
        
        :param video_id: YouTube video ID
        :return: Dictionary with video metadata including id, title, channel info,
                metrics, duration, thumbnails, and content type indicators
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        options = {
            **self.common_options,
            'extract_flat': False,  # We want full info
        }
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                
                return {
                    'id': video_id,
                    'title': info['title'],
                    'description': info.get('description'),
                    'channel_id': info.get('channel_id'),
                    'channel_title': info.get('channel', None) or info.get('uploader', None),
                    'published_at': format_datetime(
                        upload_date=info.get('upload_date'),
                        timestamp=info.get('timestamp')
                    ),
                    'duration': info.get('duration'),
                    'view_count': info.get('view_count'),
                    'like_count': info.get('like_count'),
                    'thumbnail_url': info.get('thumbnail'),
                    'is_short': info.get('duration', 0) < 60,
                    'is_live': info.get('is_live', False),
                    'tags': info.get('tags', []),
                }
                
        except Exception as e:
            print(f"Error fetching video info: {str(e)}")
            raise
        
    
    def get_video_timestamps(self, video_id: str) -> Union[List[Dict[str, Any]], None]:
        """
        Extracts chapter information from a video using yt-dlp.

        :param video_id: The YouTube video ID.
        :return: A list of chapter dictionaries (with 'start_time', 'end_time', 'title')
                or None if chapters are not available or an error occurs.
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        options = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False, # Need detailed info for chapters
            'skip_download': True, # Don't download the video
        }

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)

            chapters = info.get('chapters')

            if not chapters:
                # No chapters found by yt-dlp, which is not an error, just lack of data.
                return [] # Return empty list

            formatted_chapters = []
            for chapter in chapters:
                start_time = chapter.get('start_time')
                # Ensure start_time exists and is a number (yt-dlp should provide float/int)
                if start_time is not None and isinstance(start_time, (int, float)):
                    formatted_chapters.append({
                        'start_time': int(round(start_time)), # Store as integer seconds
                        'end_time': int(round(chapter.get('end_time'))) if chapter.get('end_time') is not None else None,
                        'title': chapter.get('title', 'Untitled Chapter')
                    })

            if not formatted_chapters:
                # If filtering removed all chapters (e.g., invalid data)
                return [] # Return empty list

            #print(f"Successfully extracted {len(formatted_chapters)} timestamps for video {video_id}.")
            return formatted_chapters

        except Exception as e:
            print(f"An unexpected error occurred fetching chapters for {video_id}: {str(e)}")
            return None
        
    
    def get_playlist_info(self, playlist_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a YouTube playlist and its videos
        
        :param playlist_id: YouTube playlist ID
        :return: dict: Playlist information including videos
        """
        url = f"https://www.youtube.com/playlist?list={playlist_id}"
        options = {
            **self.common_options,
            # extract_flat is True from common_options
            'playlistreverse': False,  # Keep original playlist order
            'playlistend': 1000,      # Attempt to retrieve all playlist items
        }
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info:
                    raise ValueError(f"Could not fetch info for playlist {playlist_id}")
                
                # Extract basic playlist information
                playlist_data = {
                    'id': info.get('id', playlist_id), # Primary key for playlists table
                    'title': info.get('title', 'Unnamed Playlist'), # For playlists table
                    'description': info.get('description', ''),    # For playlists table
                    'channel_id': info.get('channel_id'),          # For playlists table (FOREIGN KEY)
                    'video_count': info.get('playlist_count'),     # For playlists table
                    'modified_date': info.get('modified_date'),    # For playlists table (TEXT YYYYMMDD)
                    
                    # Additional contextual information (not directly in 'playlists' table but useful)
                    'channel_title': info.get('channel') or info.get('uploader'),
                    'uploader_id': info.get('uploader_id'),

                    'videos': [] # List of lightweight video dicts
                }
                
                # Process all entries (videos) in the playlist
                if 'entries' in info:
                    for entry in info['entries']:
                        if not entry:
                            continue
                            
                        video_id = entry.get('id')
                        if not video_id:
                            continue
                            
                        # Lightweight video object for the roster
                        video_entry_data = {
                            'id': video_id,
                            'title': entry.get('title', 'Unknown Video'),
                            'duration': entry.get('duration', 0),
                            'url': entry.get('url'), # Useful for direct access or later processing
                            # CANNOT include 'published_at' here because it is given as None. Only available in full video info
                        }
                        
                        playlist_data['videos'].append(video_entry_data)
                
                return playlist_data
                
        except Exception as e:
            print(f"Error fetching playlist info: {str(e)}")
            raise

    def get_raw_video_transcript(self, video_id: str, languages: List[str] = None) -> Dict[str, Any] | None:
        """
        Retrieves the best available transcript for a video with smart language detection.

        Strategy:
        1. Detects the video's original language
        2. If original is in requested languages, prioritizes that
        3. Falls back to translations only if needed
        
        Priority within each category:
        - Manual subtitles > Auto-generated
        - Original language > Translated
        
        :param video_id: The YouTube video ID
        :param languages: List of language codes in priority order (default: ['en', 'it'])
        :return: Dictionary with 'vtt' content, 'lang' code, 'source' ('manual'/'automatic'),
                and 'is_translation' (bool), or None if no suitable transcript found
        """
        if languages is None:
            languages = ['en', 'it']
        
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        options = {
            **self.common_options,
            'skip_download': True,
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': languages,
            'subtitlesformat': 'vtt',
            'extract_flat': False,
        }
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
            
            manual_subs = info.get('subtitles', {})
            auto_subs = info.get('automatic_captions', {})

            # Detect original video language
            video_language = info.get('language')  # e.g., 'it', 'en', etc.
            if not video_language:
                # Fallback: Try to infer from available subtitles
                # If only one language in manual subs, it's likely the original
                if manual_subs and len(manual_subs) == 1:
                    video_language = list(manual_subs.keys())[0]
                elif auto_subs:
                    # Check if any of our target languages has non-translated auto subs
                    for lang in languages:
                        if lang in auto_subs:
                            sample_url = auto_subs[lang][0].get('url', '')
                            if 'tlang=' not in sample_url:
                                video_language = lang
                                break
            
            # Reorder languages to prioritize original if detected
            ordered_languages = languages.copy()
            if video_language and video_language in ordered_languages:
                # Move original language to front
                ordered_languages.remove(video_language)
                ordered_languages.insert(0, video_language)

            # Priority 1: Try manual subtitles in language order
            for lang in ordered_languages:
                if lang in manual_subs and manual_subs[lang]:
                    vtt_url = self._find_vtt_url(manual_subs[lang])
                    if vtt_url:
                        is_translation = 'tlang=' in vtt_url
                        vtt_content = self._fetch_vtt_content(vtt_url, video_id)
                        if vtt_content:
                            return {
                                'vtt': vtt_content,
                                'lang': lang,
                                'source': 'manual',
                                'is_translation': is_translation,
                                'original_language': video_language
                            }
            
            # Priority 2: Try auto-generated subtitles in language order
            for lang in ordered_languages:
                if lang in auto_subs and auto_subs[lang]:
                    vtt_url = self._find_vtt_url(auto_subs[lang])
                    if vtt_url:
                        is_translation = 'tlang=' in vtt_url
                        vtt_content = self._fetch_vtt_content(vtt_url, video_id)
                        if vtt_content:
                            return {
                                'vtt': vtt_content,
                                'lang': lang,
                                'source': 'automatic',
                                'is_translation': is_translation,
                                'original_language': video_language
                            }
            
            print(f"No suitable transcript found in languages {languages} for video {video_id}")
            return None
            
        except Exception as e:
            print(f"Error fetching transcript for video {video_id}: {str(e)}")
            return None
        
        
    def _find_vtt_url(self, subtitle_formats: List[Dict], prefer_original: bool = True) -> str | None:
        """
        Find or create VTT format URL from list of subtitle formats.
        
        :param subtitle_formats: List of subtitle format dictionaries from yt-dlp
        :return: VTT URL or None
        """
        original_urls = []
        translated_urls = []

        # First pass: Categorize URLs by whether they're translations
        for fmt in subtitle_formats:
            url = fmt.get('url')
            if not url:
                continue
            
            # Check if it's already VTT format
            if fmt.get('ext') == 'vtt':
                if 'tlang=' not in url:
                    original_urls.append(url)
                else:
                    translated_urls.append(url)
            else:
                # Need to convert to VTT
                url_modified = re.sub(r'&fmt=[^&]+', '&fmt=vtt', url)
                if url_modified == url and 'fmt=' not in url:
                    separator = '&' if '?' in url else '?'
                    url_modified = f"{url}{separator}fmt=vtt"
                
                if 'tlang=' not in url_modified:
                    original_urls.append(url_modified)
                else:
                    translated_urls.append(url_modified)
                
                return url_modified
        
        # Return based on preference
        if prefer_original:
            # Try original first, then translations
            if original_urls:
                return original_urls[0]
            elif translated_urls:
                return translated_urls[0]
        else:
            # Return any available (original still preferred, but not strict)
            if original_urls:
                return original_urls[0]
            elif translated_urls:
                return translated_urls[0]
        
        return None
        

    def _fetch_vtt_content(self, vtt_url: str, video_id: str) -> str | None:
        """
        Helper method to fetch VTT content from a URL with retry logic.
        
        :param vtt_url: URL of the VTT subtitle file
        :param video_id: Video ID for error reporting
        :return: VTT content as string, or None on failure
        """

        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                # Add headers to appear more like a browser
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                    'Accept-Language': 'en-US,en;q=0.9'
                }
                response = requests.get(vtt_url, timeout=10, headers=headers)
                response.raise_for_status()
                return response.text
            
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (attempt + 1)
                        print(f"Rate limited. Waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"Max INTERNAL retries reached for video {video_id}.")
                        return None
                else:
                    print(f"HTTP error {e.response.status_code} fetching VTT for video {video_id}: {e}")
                    return None
                
            except requests.exceptions.RequestException as e:
                print(f"Error fetching VTT from {vtt_url} for video {video_id}: {e}")
                return None
        
        return None
        
    # TODO: Implement method to get the list of online available video for a channel


    def get_channel_dir(self, channel_name: str, channel_id: str) -> str:
        """
        Constructs the expected directory path for a channel.
        
        :param channel_name: The name of the channel.
        :param channel_id: The ID of the channel.
        :return: The absolute path to the channel's download directory.
        """
        sanitized_channel_name = sanitize_filename(channel_name)
        channel_folder_name = f"{sanitized_channel_name} [{channel_id}]"
        return os.path.join(self.download_dir, channel_folder_name)

    ###### DOWNLOAD METHODS #####

    def download_video(self, video_id: str, channel_id: str, channel_name: str) -> Union[str, None]:
        """
        Downloads a specific video using yt-dlp into a structured directory.

        :param video_id: The ID of the video to download.
        :param channel_id: The ID of the channel (for uniqueness).
        :param channel_name: The name of the channel (for readability).
        :return: The absolute path to the downloaded file, or None if download fails.
        """
        url = f"https://www.youtube.com/watch?v={video_id}"

        # Sanitize channel name and create folder
        sanitized_channel_name = sanitize_filename(channel_name)
        channel_folder_name = f"{sanitized_channel_name} [{channel_id}]"
        channel_dir = os.path.join(self.download_dir, channel_folder_name)
        os.makedirs(channel_dir, exist_ok=True)

        # Prepare yt-dlp options
        # Rely on yt-dlp's internal sanitization for %(title)s
        output_template = os.path.join(channel_dir, '%(title)s.%(ext)s')

        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',   # Best video/audio, merge if needed
            'outtmpl': output_template,
            'merge_output_format': 'mp4',   # Ensure merged file is mp4
            'quiet': False,
            'no_warnings': False,
            'continuedl': True,     # Resume partial downloads
            'noprogress': False,    # Show progress
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',    # Convert to mp4 if not already
            }],
            'progress_hooks': [self._download_hook], # Capture final path
            # Add this line to ignore playlists during download:
            'noplaylist': True,
            # Workaround for YouTube SABR streaming issues (403 errors)
            # Use tv_embedded or android client instead of default web client
            'extractor_args': {
                'youtube': {
                    'player_client': ['android', 'tv_embedded'],  # Bypass SABR streaming
                    'skip': ['hls', 'dash']  # Skip streaming protocols that may cause issues
                }
            },
            # Consider adding rate limits if needed:
            # 'limit_rate': '5M', # Limit download speed e.g., 5MB/s
        }

        self._final_filepath = None # Reset before download attempt

        try:
            print(f"Attempting to download video: {video_id} to folder: {channel_folder_name}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # At higher level, we will check if the file already exists
                # before calling download, so we can skip if it does.
                
                ydl.download([url])

            # Check if the hook successfully captured the path
            if self._final_filepath and os.path.exists(self._final_filepath):
                print(f"Successfully downloaded video {video_id} to {self._final_filepath}")
                return self._final_filepath
            else:
                # Fallback: Try to determine path if hook failed or file missing immediately after hook
                print(f"Warning: Download hook did not capture final path or file check failed for {video_id}. Attempting to determine path.")
                try:
                    # Re-extract info without download to use prepare_filename
                    info = ydl.extract_info(url, download=False)
                    # Construct the *expected* final path based on options and info
                    # Note: This might not perfectly match if complex post-processing occurred
                    # We need to account for the potential .mp4 extension from the postprocessor
                    base_path = ydl.prepare_filename(info)
                    base_path_no_ext, _ = os.path.splitext(base_path)
                    inferred_path_mp4 = base_path_no_ext + '.mp4'

                    if os.path.exists(inferred_path_mp4):
                        print(f"Inferred path exists: {inferred_path_mp4}")
                        return inferred_path_mp4
                    elif os.path.exists(base_path): # Check original extension path as last resort
                        print(f"Inferred path (original ext) exists: {base_path}")
                        return base_path
                    else:
                        print(f"Could not determine final file path for {video_id} via inference.")
                        return None
                except Exception as infer_e:
                    print(f"Error during path inference for {video_id}: {infer_e}")
                    return None


        except yt_dlp.utils.DownloadError as e:
            print(f"DownloadError for video {video_id}: {e}")
            # Check if it's because the video is unavailable
            if 'unavailable' in str(e).lower() or 'private' in str(e).lower():
                 print(f"Video {video_id} seems unavailable or private.")
                 # The caller (VideoManager) should handle updating the DB status
            return None # Signal download failure
        except Exception as e:
            print(f"An unexpected error occurred during download of {video_id}: {str(e)}")
            return None # Signal download failure
        finally:
            self._final_filepath = None # Clean up hook variable

    def _download_hook(self, d):
        """
        yt-dlp progress hook that captures the final filepath of downloaded videos.
        This hook is called multiple times by yt-dlp during the download process:
        - When download starts ('status': 'downloading')
        - During download progress updates
        - When download finishes ('status': 'finished')
        - After post-processing completes

        :param d: Dictionary containing download status information
        """
        hook_status = d.get('status')
        info_dict = d.get('info_dict')
        #print(f"DEBUG Hook: Status='{hook_status}', Filename='{d.get('filename')}', InfoDict Keys={list(d.get('info_dict', {}).keys())}") # Detailed debug

        final_path = None

        # Priority 1: Check info_dict['filepath'] (most reliable after post-processing)
        if info_dict:
            final_path = info_dict.get('filepath')
            if final_path:
                # Use the definitive path and stop checking
                self._final_filepath = final_path
                return

            # Priority 2: Fallback to info_dict['filename'] if filepath not set yet
            # Check if status is 'finished' or if 'filepath' key is at least present
            filename_in_info = info_dict.get('filename')
            if filename_in_info and (hook_status == 'finished' or 'filepath' in info_dict):
                # Avoid temporary fragments
                if '.f' not in os.path.basename(filename_in_info) and '.part' not in filename_in_info:
                    # Set this as a potential path, but don't return yet,
                    # 'filepath' might still appear in a later hook call.
                    self._final_filepath = filename_in_info


        # Priority 3: Last resort check for top-level 'filename' when status is 'finished'
        # Use this only if we haven't found a path via info_dict yet.
        if hook_status == 'finished' and not self._final_filepath:
            filename = d.get('filename')
            # Basic check to avoid temporary '.f*' or '.part' paths
            if filename and '.f' not in os.path.basename(filename) and '.part' not in filename:
                self._final_filepath = filename
        