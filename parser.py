import re
import yt_dlp
from typing import Union


class InputParser:
    """
    Parse YouTube URLs to identify entity type and ID.
    
    This class provides methods to parse and extract information from YouTube URLs,
    determining whether they refer to channels, playlists, videos, or shorts.
    It also identifies any associated entities (like a video within a playlist).
    """
    
    def parse_url(self, url: str) -> tuple:
        """
        Parse any YouTube URL and identify its primary entity and associated entities.
        Determines primary entity using priority: channel > playlist > video > short.

        :param url: YouTube URL to parse.
        :return: A tuple containing the primary entity type, primary entity ID,
                 associated video ID (if applicable), and associated playlist ID (if applicable).
        """

        # Check if the URL is a valid string
        if not isinstance(url, str):
            raise ValueError("ERROR: Invalid URL provided. It must be a non-empty string.")
        
        # Check if the URL is a valid YouTube URL
        if not re.search(r'(youtube\.com|youtu\.be)', url):
            raise ValueError(f"ERROR: Invalid YouTube URL: {url}")
        
        # Extract all possible IDs from the URL - each method handles its own pattern checks
        channel_id = self._extract_channel_id(url)
        playlist_id = self._extract_playlist_id(url)
        video_id = self._extract_video_id(url)
        short_id = self._extract_short_id(url)


        # Determine primary entity based on priority
        # 1. Channel has highest priority
        if channel_id:
            return 'channel', channel_id, None, None
            
        # 2. Playlist is next priority
        if playlist_id and 'youtube.com/playlist' in url:   # Ensure it's mainly a playlist URL
            return 'playlist', playlist_id, video_id, None
        
        # 3. Video is next priority
        if video_id:
            return 'video', video_id, None, playlist_id
        
        # 4. Short is final priority
        if short_id:
            return 'short', short_id, None, playlist_id
            
        # If we get here, we couldn't identify the URL
        raise ValueError(f"Unsupported YouTube URL format: {url}")
    

    def _extract_channel_id(self, url: str) -> Union[str, None]:
        """
        Extract channel ID from various YouTube channel URL formats.
    
        This method handles four types of channel URLs:
        1. Direct channel ID URLs: youtube.com/channel/UC... (returns ID directly)
        2. Custom URLs: youtube.com/c/... (requires API lookup)
        3. Handle URLs: youtube.com/@... (requires API lookup)
        4. Legacy user URLs: youtube.com/user/... (requires API lookup)

        Uses yt-dlp to resolve custom URLs and handles to actual channel IDs.
        
        :param url: YouTube channel URL.
        :return: Channel ID or None if extraction fails.
        """
        # Direct channel ID format
        channel_id_match = re.search(r'youtube\.com/channel/([^/?&]+)', url)
        if channel_id_match:
            return channel_id_match.group(1)
        
        # Custom URL format or Handle format
        custom_url_match = re.search(r'youtube\.com/c/([^/?&]+)', url)
        handle_match = re.search(r'youtube\.com/@([^/?&]+)', url)
        user_match = re.search(r'youtube\.com/user/([^/?&]+)', url)
        
        username = None
        if custom_url_match:
            username = custom_url_match.group(1)
        elif handle_match:
            username = handle_match.group(1)
        elif user_match:
            username = user_match.group(1)
            
        if username:
            try:
                # Use yt-dlp with timeout and strict error handling
                ydl_opts = {
                    'quiet': True,
                    'extract_flat': True,
                    'skip_download': True,
                    'no_warnings': True,
                    'socket_timeout': 10,  # 10 second timeout
                    'retries': 3           # Only try three times
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    if handle_match:    # Handle format with @username
                        # First try a more direct approach for handles
                        info = ydl.extract_info(f"https://www.youtube.com/@{username}/videos", download=False)
                        if info and 'channel_id' in info:
                            return info['channel_id']
                    
                    # Try the original URL as fallback
                    info = ydl.extract_info(url, download=False)
                    if info and 'channel_id' in info:
                        return info['channel_id']
                    
                    # If we still don't have it, try a search as last resort
                    #if 'entries' in info and len(info['entries']) > 0:
                    #    entry = info['entries'][0]
                    #    if 'channel_id' in entry:
                    #        return entry['channel_id']
                    
            except Exception as e:
                print(f"Error extracting channel ID from {url}: {str(e)}")
                return None
        
        return None
    

    def _extract_video_id(self, url: str) -> Union[str, None]:
        """
        Extract video ID from YouTube watch URL

        :param url: YouTube watch URL.
        :return: Video ID or None if not found.
        """
        # Match standard YouTube watch URL format
        video_id_match = re.search(r'youtube\.com/watch\?(?:[^&]+&)*v=([^&]+)', url)
        if video_id_match:
            return video_id_match.group(1)
        
        # Embedded player format
        embed_match = re.search(r'youtube\.com/embed/([^/?&]+)', url)
        if embed_match:
            return embed_match.group(1)
        
        # Legacy v format
        v_match = re.search(r'youtube\.com/v/([^/?&]+)', url)
        if v_match:
            return v_match.group(1)
        
        return None
    
    def _extract_playlist_id(self, url: str) -> Union[str, None]:
        """
        Extract playlist ID from YouTube playlist URL
        
        :param url: YouTube playlist URL.
        :return: Playlist ID or None if not found.
        """
        playlist_id_match = re.search(r'list=([^&]+)', url)
        if playlist_id_match:
            return playlist_id_match.group(1)
        
        # Direct playlist URLs (rare format without query params)
        direct_match = re.search(r'youtube\.com/playlist/([^/?&]+)', url)
        if direct_match:
            return direct_match.group(1)
        
        return None
    
    def _extract_short_id(self, url: str) -> Union[str, None]:
        """
        Extract video ID from YouTube shorts URL

        :param url: YouTube shorts URL.
        :return: Short video ID or None if not found.
        """
        short_id_match = re.search(r'youtube\.com/shorts/([^/?&]+)', url)
        if short_id_match:
            return short_id_match.group(1)
        return None