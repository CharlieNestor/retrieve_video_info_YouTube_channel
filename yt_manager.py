import pandas as pd
import numpy as np
import urllib.request
import urllib.error
import html
import yt_dlp
import sqlite3
import os
import re
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Helper function for sanitizing filenames
def sanitize_filename(name: str) -> str:
    """Removes or replaces characters unsafe for filenames."""
    # Remove characters that are definitely problematic
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Replace sequences of dots or spaces with a single underscore
    name = re.sub(r'\.+', '_', name)
    name = re.sub(r'\s+', '_', name)
    # Ensure it doesn't start/end with problematic chars like space or dot
    name = name.strip(' .')
    # Limit length (optional, but good practice)
    max_len = 200 # Example limit
    if len(name) > max_len:
        name = name[:max_len]
    return name if name else "untitled" # Ensure not empty


class YouTubeManager:
    """
    Main entry point for all YouTube operations
    """

    storage_name = 'youtube.db'
    storage_path = os.path.join(os.getenv('DOWNLOAD_DIR'), storage_name)
    
    def __init__(self, storage_path = storage_path, download_dir=os.getenv('DOWNLOAD_DIR')):
        self.parser = InputParser()
        self.storage = SQLiteStorage(storage_path)
        self.downloader = MediaDownloader(download_dir)
        self.channel_manager = ChannelManager(self.storage, self.downloader)
        self.video_manager = VideoManager(self.storage, self.downloader)
        self.playlist_manager = PlaylistManager(self.storage, self.downloader, self.video_manager)


    def process_url(self, url: str, force_update: bool = False):
        """
        Process any YouTube URL and return appropriate data. 
        This is the Entry Point for the user.

        :param url: The YouTube URL to process.
        :param force_update: If True, force update regardless of last update time. Defaults to False.
        :return: Appropriate data dictionary or raises ValueError.
        """

        primary_entity_type, primary_entity_id, associated_video_id, associated_playlist_id = self.parser.parse_url(url)
        main_result = None

        if primary_entity_type == 'channel':
            main_result = self.channel_manager.process(primary_entity_id, force_update=force_update)

        elif primary_entity_type == 'video':
            main_result = self.video_manager.process(
                video_id=primary_entity_id,
                force_update=force_update
            )
            if associated_playlist_id:
                self.playlist_manager.process(playlist_id=associated_playlist_id, force_update=force_update)

        elif primary_entity_type == 'short':
            # Shorts are processed by VideoManager
            main_result = self.video_manager.process(
                video_id=primary_entity_id,
                force_update=force_update,
                is_short=True
            )
            if associated_playlist_id:
                self.playlist_manager.process(playlist_id=associated_playlist_id, force_update=force_update)

        elif primary_entity_type == 'playlist':
            main_result = self.playlist_manager.process(
                playlist_id=primary_entity_id,
                force_update=force_update
            )
        else:
            raise ValueError(f"Unknown entity type: {primary_entity_type}")
        
        return main_result
        

class InputParser:
    """
    Parse YouTube URLs to identify entity type and ID
    """
    
    def parse_url(self, url):
        """
        Parse any YouTube URL.
        Returns: (primary_entity_type, primary_entity_id, associated_video_id, associated_playlist_id)
        - primary_entity_type: 'channel', 'video', 'playlist', 'short'
        - primary_entity_id: The ID of the main entity determined by the URL structure.
        - associated_video_id: Video ID if the primary entity is a playlist and URL also specified a video. Optional.
        - associated_playlist_id: Playlist ID if the primary entity is a video/short and URL also specified a playlist. Optional.
        """
        playlist_id_from_url = self._extract_playlist_id(url) # Extracts from 'list='
        video_id_from_url = self._extract_video_id(url)       # Extracts from 'v='

        # 1. Channel URLs are distinct.
        if 'youtube.com/channel/' in url or 'youtube.com/c/' in url or 'youtube.com/@' in url:
            channel_id = self._extract_channel_id(url)
            if channel_id:
                return 'channel', channel_id, None, None
            
        # 2. Explicit Playlist URLs (e.g., youtube.com/playlist?list=...)
        if 'youtube.com/playlist' in url and playlist_id_from_url:
            # Primary entity is the playlist.
            # video_id_from_url would be context if 'v=' was also in a /playlist URL.
            return 'playlist', playlist_id_from_url, video_id_from_url, None
        
        # 3. Watch URLs (e.g., youtube.com/watch?v=...) - can also contain a playlist.
        if 'youtube.com/watch' in url and video_id_from_url:
            # Primary entity is the video.
            # playlist_id_from_url is context if 'list=' was also present.
            return 'video', video_id_from_url, None, playlist_id_from_url
        
        # 4. Shorts URLs (e.g., youtube.com/shorts/...)
        if 'youtube.com/shorts/' in url:
            short_id = self._extract_short_id(url)
            if short_id:
                # Primary entity is the short (treated as a video).
                # playlist_id_from_url is context if 'list=' was also present (less common for shorts UI).
                return 'short', short_id, None, playlist_id_from_url
            
        #if 'youtube.com/channel/' in url or 'youtube.com/c/' in url or 'youtube.com/@' in url:
        #    return 'channel', self._extract_channel_id(url)
        #elif 'youtube.com/watch' in url:
        #    return 'video', self._extract_video_id(url)
        #elif 'youtube.com/playlist' in url:
        #    return 'playlist', self._extract_playlist_id(url)
        #elif 'youtube.com/shorts/' in url:
        #    return 'short', self._extract_short_id(url)
        #else:
        raise ValueError(f"Unsupported YouTube URL format: {url}")
    
    def _extract_channel_id(self, url):
        """Extract channel ID from various YouTube channel URL formats"""
        # Direct channel ID format
        channel_id_match = re.search(r'youtube\.com/channel/([^/?&]+)', url)
        if channel_id_match:
            return channel_id_match.group(1)
        
        # Custom URL format or Handle format
        custom_url_match = re.search(r'youtube\.com/c/([^/?&]+)', url)
        handle_match = re.search(r'youtube\.com/@([^/?&]+)', url)
        
        username = None
        if custom_url_match:
            username = custom_url_match.group(1)
        elif handle_match:
            username = handle_match.group(1)
            
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
                    # For handles, we know the exact URL structure
                    if handle_match:
                        # First try a more direct approach for handles
                        info = ydl.extract_info(f"https://www.youtube.com/@{username}/videos", download=False)
                        if info and 'channel_id' in info:
                            return info['channel_id']
                    
                    # Try the original URL as fallback
                    info = ydl.extract_info(url, download=False)
                    if info and 'channel_id' in info:
                        return info['channel_id']
                    
                    # If we still don't have it, try a search as last resort
                    if 'entries' in info and len(info['entries']) > 0:
                        entry = info['entries'][0]
                        if 'channel_id' in entry:
                            return entry['channel_id']
                    
            except Exception as e:
                print(f"Error extracting channel ID from {url}: {str(e)}")
                # Return username as fallback - at least we have something
                return f"username:{username}"
        
        return None
        
    def _extract_video_id(self, url):
        """Extract video ID from YouTube watch URL"""
        video_id_match = re.search(r'youtube\.com/watch\?(?:[^&]+&)*v=([^&]+)', url)
        if video_id_match:
            return video_id_match.group(1)
        return None
        
    def _extract_playlist_id(self, url):
        """Extract playlist ID from YouTube playlist URL"""
        playlist_id_match = re.search(r'list=([^&]+)', url)
        if playlist_id_match:
            return playlist_id_match.group(1)
        return None
        
    def _extract_short_id(self, url):
        """Extract video ID from YouTube shorts URL"""
        short_id_match = re.search(r'youtube\.com/shorts/([^/?&]+)', url)
        if short_id_match:
            return short_id_match.group(1)
        return None
    

class SQLiteStorage:
    def __init__(self, db_path):
        """
        Initialize database connection and create schema if needed
        """
        self.db_path = db_path
        self.conn = None
        self._connect()
        self._create_schema()
    
    def _connect(self):
        """
        Establish connection to SQLite database
        """
        self.conn = sqlite3.connect(self.db_path)
        # Enable foreign key constraints
        self.conn.execute("PRAGMA foreign_keys = ON")
        # Return dictionaries instead of tuples
        self.conn.row_factory = sqlite3.Row


    def _check_tables_exist(self):
        """Check if all required tables exist"""
        cursor = self.conn.cursor()
        required_tables = ['channels', 'videos', 'playlists']
        
        for table in required_tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            if not cursor.fetchone():
                return False
        return True

    
    def _create_schema(self):
        """
        Create database schema if tables don't exist
        """

        # Check if schema already exists
        if self._check_tables_exist():
            #print("Database schema already exists")
            return
        
        # Create tables for our schema
        cursor = self.conn.cursor()
        cursor.executescript("""
        -- Entity types table
        CREATE TABLE entity_types (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE -- 'channel', 'video', 'playlist'
        );
        
        -- Channels table
        CREATE TABLE channels (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            subscriber_count INTEGER,
            video_count INTEGER,
            thumbnail_url TEXT,
            content_breakdown TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        -- Videos table
        CREATE TABLE videos (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            channel_id TEXT NOT NULL,
            channel_title TEXT,
            playlist_id TEXT DEFAULT NULL,
            published_at TIMESTAMP,
            duration INTEGER, -- in seconds
            view_count INTEGER,
            like_count INTEGER,
            thumbnail_url TEXT,
            is_short BOOLEAN DEFAULT 0,
            is_live BOOLEAN DEFAULT 0,
            file_path TEXT,
            transcript_path TEXT,
            downloaded BOOLEAN DEFAULT 0,
            download_date TIMESTAMP,
            status TEXT DEFAULT 'available', -- 'available', 'unavailable'
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE,
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE SET NULL
        );

        -- Playlists table
        CREATE TABLE playlists (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            channel_id TEXT NOT NULL,
            video_count INTEGER DEFAULT 0,
            modified_date TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
        );

        -- Tags table
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        );
        
        -- Video-Tag relations
        CREATE TABLE video_tags (
            video_id TEXT,
            tag_id INTEGER,
            PRIMARY KEY (video_id, tag_id),
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );
        
        -- Timestamps table
        CREATE TABLE timestamps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            video_id TEXT,
            time_seconds INTEGER,
            description TEXT,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        );

        """)
        self.conn.commit()
        print("Database schema created successfully")

    # Channel operations
    def save_channel(self, channel_data: dict):
        """Insert or update channel information"""
        cursor = self.conn.cursor()
        
        # Extract only the profile picture URL from the thumbnail dictionary
        thumbnail_url = None
        if isinstance(channel_data.get('thumbnail_url'), dict):
            thumbnail_url = channel_data.get('thumbnail_url', {}).get('profile_picture')
        else:
            thumbnail_url = channel_data.get('thumbnail_url')
            
        # Use the total video count directly
        video_count = channel_data.get('video_count')
        
        # Convert content_breakdown to JSON string if it's a dictionary
        content_breakdown = channel_data.get('content_breakdown')
        if isinstance(content_breakdown, dict):
            content_breakdown = json.dumps(content_breakdown)
        
        # SQL for inserting a new channel or updating an existing one.
        # created_at is set to CURRENT_TIMESTAMP on initial insert.
        # last_updated is set to CURRENT_TIMESTAMP on both insert and update.
        # On conflict (update), created_at is NOT modified.
        sql = """
            INSERT INTO channels (
                id, name, description, subscriber_count, video_count, 
                thumbnail_url, content_breakdown, 
                created_at, 
                last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                description = excluded.description,
                subscriber_count = excluded.subscriber_count,
                video_count = excluded.video_count,
                thumbnail_url = excluded.thumbnail_url,
                content_breakdown = excluded.content_breakdown,
                last_updated = CURRENT_TIMESTAMP
        """
        params = (
            channel_data['id'],
            channel_data['name'],
            channel_data.get('description'),
            channel_data.get('subscriber_count'),
            video_count,
            thumbnail_url,
            content_breakdown
        )
        cursor.execute(sql, params)
        self.conn.commit()
    
    def get_channel(self, channel_id: str):
        """Get channel by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
        row = cursor.fetchone()
        return dict(row) if row else None # Convert Row to dict if found
    
    def channel_exists(self, channel_id: str) -> bool:
        """Check if channel exists in database"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM channels WHERE id = ?", (channel_id,))
        return cursor.fetchone() is not None
    
    def list_channels(self, limit: int = None, sort_by: str = "name"):
        """List channels with pagination and sorting"""
        cursor = self.conn.cursor()
        query = "SELECT id, name FROM channels"
        if sort_by:
            if sort_by in ['id', 'name']:
                query += f" ORDER BY {sort_by}"
            else:
                print(f"WARNING: Invalid sort_by column: {sort_by}. Defaulting to name.")
                query += " ORDER BY name"
        if limit:
            query += f" LIMIT {limit}"
        try:
            cursor.execute(query)
            rows = cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            print(f"Error listing channels: {e}")
            return []

    
    def delete_channel(self, channel_id: str, cascade: bool = False):
        """Delete channel and optionally its videos"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        if cascade:
            cursor.execute("DELETE FROM videos WHERE channel_id = ?", (channel_id,))
        self.conn.commit()

    
    # Video operations
    def save_video(self, video_data: dict):
        """Insert or update video information"""
        cursor = self.conn.cursor()
        
        # Extract thumbnail URL if it's a complex object
        thumbnail_url = video_data.get('thumbnail_url')
        if isinstance(thumbnail_url, dict) and 'url' in thumbnail_url:
            thumbnail_url = thumbnail_url['url']

        # SQL for inserting a new video or updating an existing one.
        # Fields like file_path, downloaded, etc., are given default values for the INSERT part.
        # On conflict (update), these specific fields are NOT updated, preserving their existing values.
        sql = """
            INSERT INTO videos (
                id, title, description, channel_id, channel_title, playlist_id,
                published_at, duration, view_count, like_count,
                thumbnail_url, is_short, is_live, status, 
                file_path, transcript_path, downloaded, download_date,
                last_updated
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, -- 14 fields from video_data
                ?, ?, ?, ?,                               -- 4 fields: file_path, transcript_path, downloaded, download_date
                CURRENT_TIMESTAMP                         -- last_updated
            )
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                -- channel_id = excluded.channel_id, -- channel_id should not change for an existing video ID.
                channel_title = excluded.channel_title,
                -- playlist_id = excluded.playlist_id, -- playlist_id should be managed by playlist processing
                published_at = excluded.published_at,
                duration = excluded.duration,
                view_count = excluded.view_count,
                like_count = excluded.like_count,
                thumbnail_url = excluded.thumbnail_url,
                is_short = excluded.is_short,
                is_live = excluded.is_live,
                status = excluded.status,
                last_updated = CURRENT_TIMESTAMP
            -- Columns NOT updated by this general save_video if the video already exists:
            -- file_path, transcript_path, downloaded, download_date.
            -- These should be updated by their specific dedicated methods.
        """
        params = (
            video_data['id'],
            video_data['title'],
            video_data.get('description'),
            video_data['channel_id'],
            video_data.get('channel_title'),
            video_data.get('playlist_id'),
            video_data.get('published_at'),
            video_data.get('duration'),
            video_data.get('view_count'),
            video_data.get('like_count'),
            thumbnail_url,
            video_data.get('is_short', False),
            video_data.get('is_live', False),
            video_data.get('status', 'available'),
            video_data.get('file_path'),
            video_data.get('transcript_path'),
            video_data.get('downloaded', 0),
            video_data.get('download_date') 
        )
        cursor.execute(sql, params)
        self.conn.commit()

    def save_video_tags(self, video_id: str, tags: List[str]):
        """
        Saves or updates the tags for a specific video.
        Deletes existing tag associations before adding new ones.

        :param video_id: The ID of the video.
        :param tags: A list of tag names (strings) for the video.
        """
        if not video_id:
            print("ERROR: video_id cannot be empty when saving tags.")
            return False # Indicate failure

        cursor = self.conn.cursor()

        try:
            # 1. Check if the video actually exists
            cursor.execute("SELECT 1 FROM videos WHERE id = ?", (video_id,))
            if not cursor.fetchone():
                print(f"WARNING: Video with ID {video_id} not found. Cannot save tags.")
                return False # Indicate failure

            # 2. Delete existing tag associations for this video
            cursor.execute("DELETE FROM video_tags WHERE video_id = ?", (video_id,))

            # 3. Process and link new tags (only if tags list is provided and not empty)
            if tags: # Proceed only if there are tags to add
                processed_count = 0
                for tag_name in tags:
                    if not tag_name or not isinstance(tag_name, str):
                        continue

                    normalized_tag = tag_name.lower().strip()
                    if not normalized_tag:
                        continue

                    # Insert tag into 'tags' table if it doesn't exist
                    cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (normalized_tag,))

                    # Get the ID of the tag
                    cursor.execute("SELECT id FROM tags WHERE name = ?", (normalized_tag,))
                    tag_row = cursor.fetchone()

                    if tag_row:
                        tag_id = tag_row['id']
                        # Link video and tag in 'video_tags' table
                        cursor.execute("INSERT OR IGNORE INTO video_tags (video_id, tag_id) VALUES (?, ?)", (video_id, tag_id))
                        processed_count += 1
                    else:
                        print(f"WARNING: Could not retrieve ID for tag '{normalized_tag}' for video {video_id}.")
                
                if processed_count > 0:
                    print(f"Successfully saved {processed_count} tags for video {video_id}.")
                else: 
                    print(f"WARNING: No valid tags were processed for video {video_id} from the provided list.")
            else:
                 print(f"No new tags provided for video {video_id}. Only cleared existing tags.") # Optional logging


            # 4. Commit the transaction
            self.conn.commit()
            return True # Indicate success

        except sqlite3.Error as e:
            print(f"Database error saving tags for video {video_id}: {e}")
            self.conn.rollback() # Rollback changes on error
            return False # Indicate failure
        except Exception as e:
            print(f"An unexpected error occurred saving tags for video {video_id}: {e}")
            self.conn.rollback()
            return False # Indicate failure


    def save_video_timestamps(self, video_id: str, timestamps: List[Dict[str, Any]]) -> bool:
        """
        Saves video chapters/timestamps to the database.
        Deletes existing timestamps for the video before inserting new ones.

        :param video_id: The ID of the video.
        :param timestamps: A list of dictionaries, each with 'start_time' (int) and 'title' (str).
        :return: True if saving was successful, False otherwise.
        """
        cursor = self.conn.cursor()
        
        try:
            # 1. Delete existing timestamps for this video
            cursor.execute("DELETE FROM timestamps WHERE video_id = ?", (video_id,))
            
            data_to_insert = []
            # 2. Prepare data for bulk insert
            # Map the input dict keys to the table columns (time_seconds, description)
            data_to_insert = [
                (video_id, ts['start_time'], ts['title'])
                for ts in timestamps
                if 'start_time' in ts and 'title' in ts # Basic validation
            ]

            if not data_to_insert:
                print(f"WARNING: No valid timestamp data found in the provided list for {video_id}.")
                # Still commit the delete operation
                self.conn.commit()
                return True

            # 3. Bulk insert the new timestamps
            cursor.executemany("""
                INSERT INTO timestamps (video_id, time_seconds, description)
                VALUES (?, ?, ?)
            """, data_to_insert)
            
            # 4. Commit the transaction
            self.conn.commit()
            print(f"Successfully saved {len(data_to_insert)} timestamps for video {video_id}.")

            return True
            
        except sqlite3.Error as e:
            print(f"Database error saving timestamps for video {video_id}: {e}")
            self.conn.rollback() # Rollback changes on error
            return False
        except Exception as e:
            print(f"An unexpected error occurred saving timestamps for video {video_id}: {e}")
            self.conn.rollback()
            return False
        
    

    def get_video(self, video_id: str):
        """Get video by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = cursor.fetchone()
        return dict(row) if row else None # Convert Row to dict if found

    def video_exists(self, video_id: str):
        """Check if video exists in database"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM videos WHERE id = ?", (video_id,))
        return cursor.fetchone() is not None
    
    def get_channel_videos(self, channel_id: str, limit: int = None) -> List[dict]:
        """Get videos for a specific channel with optional pagination"""
        cursor = self.conn.cursor()
        query = "SELECT id, title FROM videos WHERE channel_id = ? ORDER BY published_at DESC"
        if limit:
            query += f" LIMIT {limit}"
        try:
            cursor.execute(query, (channel_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            print(f"Error getting channel videos: {e}")
            return []
    
    def delete_video(self, video_id: str):
        """Delete video from database"""
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        self.conn.commit()

    def list_tags(self, limit: Optional[int] = None, sort_by: str = "name", sort_order: str = "ASC") -> List[str]:
        """
        Lists all unique tag names from the 'tags' table.

        :param limit: Optional. The maximum number of tags to return.
        :param sort_by: The column to sort by (e.g., "name", "id"). Defaults to "name".
        :param sort_order: The order of sorting ("ASC" or "DESC"). Defaults to "ASC".
        :return: A list of tag names.
        """
        cursor = self.conn.cursor()
        # Basic validation for sort_by to prevent SQL injection if it were user-facing without sanitization
        allowed_sort_columns = ["name", "id"]
        if sort_by not in allowed_sort_columns:
            sort_by = "name" # Default to a safe column

        if sort_order.upper() not in ["ASC", "DESC"]:
            sort_order = "ASC"

        query = f"SELECT name FROM tags ORDER BY {sort_by} {sort_order}"
        params = []

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [row['name'] for row in rows] if rows else []
        except sqlite3.Error as e:
            print(f"Database error listing tags: {e}")
            return []
        
    def get_tags_video(self, video_id: str) -> List[str]:
        """
        Retrieves all tag names associated with a specific video.

        :param video_id: The ID of the video.
        :return: A list of tag names for the video, or an empty list if none are found or video doesn't exist.
        """
        cursor = self.conn.cursor()
        query = """
            SELECT t.name
            FROM tags t
            JOIN video_tags vt ON t.id = vt.tag_id
            WHERE vt.video_id = ?
            ORDER BY t.name ASC;
        """
        try:
            cursor.execute(query, (video_id,))
            rows = cursor.fetchall()
            return [row['name'] for row in rows] if rows else []
        except sqlite3.Error as e:
            print(f"Database error getting tags for video {video_id}: {e}")
            return []
        
    def get_tags_channel(self, channel_id: str, limit: Optional[int] = None, min_video_count: int = 1) -> List[Dict[str, Any]]:
        """
        Retrieves all unique tags used by videos belonging to a specific channel,
        along with the count of videos in that channel using each tag.

        :param channel_id: The ID of the channel.
        :param limit: Optional. The maximum number of unique tags to return (ordered by most used).
        :param min_video_count: Minimum number of videos a tag must be associated with in this channel to be included.
        :return: A list of dictionaries, each containing 'tag_name' and 'video_count',
                 or an empty list if no relevant tags are found.
        """
        cursor = self.conn.cursor()
        query = """
            SELECT t.name AS tag_name, COUNT(DISTINCT v.id) AS video_count
            FROM tags t
            JOIN video_tags vt ON t.id = vt.tag_id
            JOIN videos v ON vt.video_id = v.id
            WHERE v.channel_id = ?
            GROUP BY t.name
            HAVING COUNT(DISTINCT v.id) >= ?
            ORDER BY video_count DESC, t.name ASC
        """
        params = [channel_id, min_video_count]

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            # Convert sqlite3.Row objects to dictionaries
            return [dict(row) for row in rows] if rows else []
        except sqlite3.Error as e:
            print(f"Database error getting tags for channel {channel_id}: {e}")
            return []
        
    def get_video_timestamps(self, video_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all timestamps (chapters) for a specific video.

        :param video_id: The ID of the video.
        :return: A list of dictionaries, each representing a timestamp 
                 (e.g., {'time_seconds': 0, 'description': 'Intro'}).
                 Returns an empty list if no timestamps are found or video doesn't exist.
        """
        cursor = self.conn.cursor()
        query = """
            SELECT time_seconds, description
            FROM timestamps
            WHERE video_id = ?
            ORDER BY time_seconds ASC;
        """
        try:
            cursor.execute(query, (video_id,))
            rows = cursor.fetchall()
            # Convert sqlite3.Row objects to dictionaries
            return [dict(row) for row in rows] if rows else []
        except sqlite3.Error as e:
            print(f"Database error getting timestamps for video {video_id}: {e}")
            return []

    def _update_video_status(self, video_id: str, status: str):
        """
        Update the status of a video.
        Returns True on success, False otherwise.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                UPDATE videos SET
                    status = ?
                WHERE id = ?
            """, (status, video_id))
            self.conn.commit()
            if cursor.rowcount > 0:
                print(f"Successfully updated status for video {video_id} to {status}")
                return True
            else:
                return False
            
        except Exception as e:
            print(f"Error updating status for video {video_id} in DB: {e}") # Keep error print for debugging
            self.conn.rollback()
            return False
    
    def _update_video_download_status(self, video_id: str, file_path: str) -> bool:
        """
        Update video record with download status and file path.
        Returns True on success, False otherwise.

        :param video_id: ID of the video to update.
        :param file_path: Absolute path to the downloaded video file.
        :return: True if update was successful, False otherwise.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                UPDATE videos SET
                    file_path = ?,
                    downloaded = 1,
                    download_date = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (file_path, video_id))
            self.conn.commit()
            if cursor.rowcount > 0:
                print(f"Successfully updated download status for video {video_id}")
                return True
            else:
                return False
        except Exception as e:
            print(f"Error updating download status for video {video_id} in DB: {e}") # Keep error print
            self.conn.rollback()
            return False
    
    def _update_video_playlist_id(self, video_id: str, playlist_id: str) -> bool:
        """
        Update only the playlist_id for a given video.
        Returns True on success, False otherwise.
        """
        cursor = self.conn.cursor()
        try:
            cursor.execute("""
                UPDATE videos SET
                    playlist_id = ?
                WHERE id = ? AND playlist_id IS NULL -- Optionally only update if not already set
            """, (playlist_id, video_id))
            self.conn.commit()
            if cursor.rowcount > 0:
                print(f"Successfully updated playlist_id for video {video_id}")
                return True
            else:
                return False
        except Exception as e:
            print(f"Error updating playlist_id for video {video_id} in DB: {e}") # Keep error print
            self.conn.rollback()
            return False

    # Playlist operations
    def save_playlist(self, playlist_data: dict):
        """Insert or update playlist information"""
        cursor = self.conn.cursor()

        # Ensure channel_id exists before saving playlist
        channel_id = playlist_data.get('channel_id')
        if not channel_id:
            raise ValueError("Cannot save playlist without a channel_id")
        
        cursor.execute("""
            INSERT OR REPLACE INTO playlists (
                id, title, description, channel_id, 
                video_count, modified_date, last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            playlist_data['id'],
            playlist_data['title'],
            playlist_data.get('description'),
            channel_id,
            playlist_data.get('video_count', 0),
            playlist_data.get('modified_date'),
        ))
        self.conn.commit()
        
        # If playlist contains videos, save them too
        if 'videos' in playlist_data and playlist_data['videos']:
            updated_count = 0
            for video in playlist_data['videos']:
                video_id = video.get('id')
                if video_id:
                    # Use the lightweight update method
                    if self._update_video_playlist_id(video_id, playlist_data['id']):
                        updated_count += 1
            
            if updated_count > 0:
                print(f"Linked {updated_count} existing videos to playlist {playlist_data['title']}")

    def get_playlist(self, playlist_id: str) -> Optional[dict]:
        """Get playlist by ID"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    

    def get_videos_by_playlist(self, playlist_id: str, limit: int = 0, offset: int = 0, sort_by: str = "published_at", sort_order: str = "DESC") -> List[dict]:
        """
        Get videos associated with a specific playlist from the database.

        :param playlist_id: The ID of the playlist.
        :param limit: Maximum number of videos to return. 0 or negative for no limit.
        :param offset: Offset for pagination.
        :param sort_by: Column to sort videos by (e.g., 'published_at', 'title', 'view_count', 'duration').
        :param sort_order: 'ASC' or 'DESC'.
        :return: A list of video dictionaries.
        """
        cursor = self.conn.cursor()
        
        allowed_sort_columns = ['published_at', 'title', 'view_count', 'duration', 'last_updated', 'id']
        if sort_by not in allowed_sort_columns:
            print(f"WARNING: Invalid sort_by column '{sort_by}' for get_videos_by_playlist. Defaulting to 'published_at'.")
            sort_by = 'published_at'
        
        if sort_order.upper() not in ['ASC', 'DESC']:
            print(f"WARNING: Invalid sort_order '{sort_order}' for get_videos_by_playlist. Defaulting to 'DESC'.")
            sort_order = 'DESC'

        query = f"SELECT * FROM videos WHERE playlist_id = ? ORDER BY {sort_by} {sort_order}"
        params = [playlist_id]
        
        if limit > 0:
            query += " LIMIT ?"
            params.append(limit)
            if offset > 0: # Offset typically used with limit
                query += " OFFSET ?"
                params.append(offset)
        
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except sqlite3.Error as e:
            print(f"Database error in get_videos_by_playlist for playlist {playlist_id}: {e}")
            return []

    def close(self):
        """Close the database connection"""
        if self.conn:
            self.conn.close()


class MediaDownloader:
    def __init__(self, download_dir: str):
        """
        Initialize MediaDownloader
        
        :param download_dir: Directory where videos will be downloaded
        """
        self.download_dir = os.path.abspath(download_dir)
        os.makedirs(self.download_dir, exist_ok=True)
        self._filename_sanitizer = None # Temporary storage for hook result
        
        # Common yt-dlp options
        self.common_options = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Do not download video by default
        }


    def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """
        Get channel information
        
        :param channel_id: YouTube channel ID
        :return: dict: Channel information
        """
        url = f"https://www.youtube.com/channel/{channel_id}"
        options = {
            **self.common_options,
            'extract_flat': True,
        }
        MIN_ENTRIES_FOR_FLAT_ASSUMPTION = 10 # Threshold
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                
                # Handle CHANNEL THUMBNAILS
                # Get just the original profile picture and banner
                thumbnails = {
                    'profile_picture': None,  # Original avatar
                    'banner': None           # Original banner
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


    def _format_datetime(self, upload_date: Optional[str] = None, timestamp: Optional[int] = None) -> Optional[str]:
        """
        Convert YouTube date/time information to ISO format
        
        :param upload_date: Date in YYYYMMDD format (e.g., '20210310')
        :param timestamp: Unix timestamp (e.g., 1615358397)
        :return: str: ISO formatted datetime or None if conversion fails
        """
        try:
            if timestamp:
                # Use timestamp for most precise datetime
                dt = datetime.fromtimestamp(timestamp)
                return dt.isoformat() + 'Z'
            elif upload_date:
                # Fallback to just date if no timestamp
                dt = datetime.strptime(upload_date, '%Y%m%d')
                return dt.date().isoformat()
            return None
        except Exception as e:
            print(f"Error formatting date: {str(e)}")
            return None
            

    def get_video_info(self, video_id: str) -> Dict[str, Any]:
        """
        Get detailed information about a specific video
        
        :param video_id: YouTube video ID
        :return: dict: Video information
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
                    'published_at': self._format_datetime(
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


    def get_video_timestamps(self, video_id: str) -> Optional[List[Dict[str, Any]]]:
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
                # No chapters found, which is not an error, just lack of data.
                return None

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
                return None

            #print(f"Successfully extracted {len(formatted_chapters)} timestamps for video {video_id}.")
            return formatted_chapters

        except yt_dlp.utils.DownloadError as e:
             # Handle cases where the video is unavailable etc.
             if 'unavailable' in str(e).lower() or 'private' in str(e).lower():
                 print(f"Video {video_id} is unavailable or private, cannot fetch chapters.")
             else:
                 print(f"yt-dlp DownloadError while fetching chapters for {video_id}: {e}")
             return None
        except Exception as e:
            print(f"An unexpected error occurred fetching chapters for {video_id}: {str(e)}")
            return None


    def get_video_transcript(self, video_id: str, lang: str = 'en') -> Optional[str]:
        """
        Fetches the video transcript using yt-dlp to find the URL, then downloads
        the content directly.

        Prioritizes specified language, with fallback (e.g., 'en-orig' for 'en').
        Prefers VTT format for download if available.

        :param video_id: The YouTube video ID.
        :param lang: The primary language code (e.g., 'en', 'es'). Defaults to 'en'.
        :return: A single string containing the raw transcript content,
                 or None if no suitable transcript URL is found or download fails.
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        options = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'listsubtitles': True, # Get list of available subtitles/captions
        }

        print(f"Attempting to find transcript URL for video {video_id} (lang={lang})...")
        transcript_url = None
        transcript_ext = None
        selected_lang = None

        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)

            # --- Optimized Language and Format Selection ---
            languages_to_try = [lang]
            # Add common fallback like 'en-orig' if primary is 'en'
            if lang == 'en':
                languages_to_try.append('en-orig')
            # Add more fallbacks if needed, e.g., lang.split('-')[0]

            subs_formats_list = None
            auto_captions = info.get('automatic_captions', {})
            manual_subtitles = info.get('subtitles', {})

            for try_lang in languages_to_try:
                if try_lang in auto_captions:
                    subs_formats_list = auto_captions[try_lang]
                    selected_lang = try_lang
                    print(f"Found automatic captions for language: {selected_lang}")
                    break # Prefer auto-captions if primary lang matches
                elif try_lang in manual_subtitles:
                    subs_formats_list = manual_subtitles[try_lang]
                    selected_lang = try_lang
                    print(f"Found manual subtitles for language: {selected_lang}")
                    break # Found in manual subs

            if not subs_formats_list:
                print(f"No transcript URL found for language '{lang}' (or fallbacks) for video {video_id}.")
                available_auto = list(auto_captions.keys())
                available_manual = list(manual_subtitles.keys())
                if available_auto or available_manual:
                    print(f"  Available auto languages: {available_auto}")
                    print(f"  Available manual languages: {available_manual}")
                return None

            # Now subs_formats_list contains [{'ext': ..., 'url': ...}, ...]
            # Select the best URL based on format priority
            found_subs = {fmt.get('ext'): fmt.get('url') for fmt in subs_formats_list if fmt.get('ext') and fmt.get('url')}

            priority_order = ['vtt', 'srv3', 'srv2', 'srv1', 'ttml'] # Prefer text formats
            for ext in priority_order:
                if ext in found_subs:
                    transcript_url = found_subs[ext]
                    transcript_ext = ext
                    break

            # Fallback if only non-preferred formats were found
            if not transcript_url and found_subs:
                 transcript_ext = list(found_subs.keys())[0]
                 transcript_url = found_subs[transcript_ext]

            if not transcript_url:
                 print(f"Failed to select a suitable transcript URL for video {video_id} (lang: {selected_lang}) from found formats: {list(found_subs.keys())}")
                 return None
            # --- End Selection ---


            print(f"Found transcript URL (lang: {selected_lang}, format: {transcript_ext}). Attempting download...")
            # print(f"DEBUG URL: {transcript_url}") # Optional debug

            # --- Direct Download with Improved Headers ---
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/97.0.4692.20 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.9', # Prioritize US English then general English
                # 'Sec-Fetch-Mode': 'navigate', # Often less critical for direct asset fetches
            }
            request = urllib.request.Request(transcript_url, headers=headers)

            with urllib.request.urlopen(request, timeout=20) as response: # Increased timeout slightly
                if response.getcode() == 200:
                    charset = response.info().get_content_charset() or 'utf-8'
                    raw_transcript_data = response.read().decode(charset)
                    print(f"Successfully downloaded raw transcript for video {video_id} (lang: {selected_lang}, format: {transcript_ext}, length: {len(raw_transcript_data)} chars).")
                    return raw_transcript_data
                else:
                    print(f"Failed to download transcript for {video_id}. Status code: {response.getcode()}")
                    return None
            # --- End Download ---

        except yt_dlp.utils.DownloadError as e:
             if 'unavailable' in str(e).lower() or 'private' in str(e).lower():
                 print(f"Video {video_id} is unavailable or private, cannot find transcript URL.")
             else:
                 print(f"yt-dlp DownloadError while fetching info for {video_id}: {e}")
             return None
        except urllib.error.URLError as e:
            print(f"URL Error downloading transcript for {video_id} from {transcript_url}: {e.reason}")
            return None
        except Exception as e:
            # import traceback # Uncomment for detailed debugging
            # print(traceback.format_exc()) # Uncomment for detailed debugging
            print(f"An unexpected error occurred fetching transcript for {video_id}: {str(e)}")
            return None
            

    def get_channel_videos_overview(self, channel_id: str) -> Dict[str, Any]:
        """
        Get an overview of videos available on a channel, categorized by type
        without downloading detailed information for each video.

        :param channel_id: YouTube channel ID
        :return: dict: Overview of channel videos by category with counts and sample videos
        """
        url = f"https://www.youtube.com/channel/{channel_id}"
        options = {
            **self.common_options,
            'extract_flat': True
        }
        
        try:
            with yt_dlp.YoutubeDL(options) as ydl:
                info = ydl.extract_info(url, download=False)
                
                if not info or 'entries' not in info:
                    return None
                
                # Prepare result structure
                possible_categories = ['Videos', 'Shorts', 'Live']
                result = {
                    'channel_id': channel_id,
                    'channel_name': info.get('channel', None) or info.get('title', None),
                    'categories': {},
                    'total_videos': 0
                }
                
                # Parse all content categories
                for content_type in info['entries']:
                    for category in possible_categories:
                        if category in content_type.get('title', ''):
                            category_title = category
                            video_count = content_type.get('playlist_count', 0)
                            break
                    
                    # Skip empty categories
                    if video_count == 0:
                        continue
                    
                    result['total_videos'] += video_count
                    
                    # Get all videos for this category
                    video_list = []
                    if 'entries' in content_type:
                        for entry in content_type['entries']:
                            video_id = entry.get('id')
                            title = entry.get('title', 'Unknown video')
                            
                            if video_id:
                                video_list.append({
                                    'id': video_id,
                                    'title': title,
                                    'upload_date': entry.get('upload_date'),
                                    'duration': entry.get('duration', 0),
                                })
                    
                    result['categories'][category_title] = {
                        'count': video_count,
                        'videos': video_list
                    }
                    
                return result
                
        except Exception as e:
            print(f"Error fetching channel videos overview: {str(e)}")
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
                    'title': info.get('title', 'Unknown Playlist'), # For playlists table
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
                        }
                        
                        playlist_data['videos'].append(video_entry_data)
                
                return playlist_data
                
        except Exception as e:
            print(f"Error fetching playlist info: {str(e)}")
            raise


    def download_video(self, video_id: str, channel_id: str, channel_name: str) -> Optional[str]:
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
            'format': 'bestvideo+bestaudio/best', # Best video/audio, merge if needed
            'outtmpl': output_template,
            'merge_output_format': 'mp4', # Ensure merged file is mp4
            'quiet': False,
            'no_warnings': False,
            'continuedl': True, # Resume partial downloads
            'noprogress': False, # Show progress
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4', # Convert to mp4 if not already
            }],
            'progress_hooks': [self._download_hook], # Capture final path
            # Add this line to ignore playlists during download:
            'noplaylist': True,
            # Consider adding rate limits if needed:
            # 'limit_rate': '5M', # Limit download speed e.g., 5MB/s
        }

        self._final_filepath = None # Reset before download attempt

        try:
            print(f"Attempting to download video: {video_id} to folder: {channel_folder_name}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Small check to see if the *exact* file path yt-dlp *might* create already exists
                # This is not foolproof due to sanitization/extension changes, but a basic check.
                # A more robust check would happen in the manager *before* calling download.
                # info_dict_pre = ydl.extract_info(url, download=False)
                # potential_path = ydl.prepare_filename(info_dict_pre)
                # if os.path.exists(potential_path):
                #     print(f"File may already exist: {potential_path}. Skipping download.")
                #     # Return the existing path assuming it's correct. Needs verification.
                #     return potential_path
                
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
        """yt-dlp hook to capture filename when download finishes."""
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



class ChannelManager:
    def __init__(self, storage: SQLiteStorage, downloader: MediaDownloader):
        """
        Initialize ChannelManager
        
        :param storage: SQLiteStorage instance for data persistence
        :param downloader: MediaDownloader instance for fetching data
        """
        self.storage = storage
        self.downloader = downloader

    def process(self, channel_id: str, force_update: bool = False):
        """
        Process a channel: fetch info, store in database, return data
        
        :param channel_id: YouTube channel ID
        :param force_update: If True, force update regardless of last update time. Defaults to False.
        :return: dict: Channel information
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
        Update channel information and its videos
        
        :param channel_id: YouTube channel ID
        :return: dict: Updated channel information
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
    
    
    def _needs_update(self, existing_channel: dict, days: int = 30) -> bool:
        """
        Determine if a channel needs to be updated based on its last update time
        
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
            
            # Handle different possible formats
            if 'T' in last_updated_str:  # ISO format with T separator
                if last_updated_str.endswith('Z'):
                    # ISO format with Z timezone indicator
                    last_updated_str = last_updated_str.replace('Z', '+00:00')
                last_updated = datetime.fromisoformat(last_updated_str)
            else:
                # Standard SQLite format
                last_updated = datetime.strptime(last_updated_str, '%Y-%m-%d %H:%M:%S')
            
            # Get current time
            now = datetime.now()

            # Calculate time difference
            time_difference = now - last_updated
            update_threshold_seconds = days * 24 * 60 * 60

            needs_update = time_difference.total_seconds() > update_threshold_seconds
            if needs_update:
                 print(f"Video {existing_channel.get('id')} needs update. Last updated: {last_updated_str} ({time_difference.days} days ago).")
            # else:
            #      print(f"Video {existing_video.get('id')} is up-to-date. Last updated: {last_updated_str} ({time_difference.days} days ago).")
            return needs_update
        except Exception as e:
            print(f"Error parsing timestamp: {str(e)}")
            # If we can't parse the timestamp, better to update
            return True

    def get_channel_videos(self, channel_id: str, limit: int = 100, offset: int = 0):
        """
        Get videos for a channel from the database
        
        :param channel_id: YouTube channel ID
        :param limit: Maximum number of videos to return, defaults to 100
        :param offset: Pagination offset, defaults to 0
        :return: list: List of video dictionaries
        """
        # Verify channel exists
        if not self.storage.channel_exists(channel_id):
            print(f"Channel {channel_id} not found in database")
            return []
            
        # Retrieve videos from database
        videos = self.storage.get_channel_videos(channel_id, limit=limit, offset=offset)
        
        # Convert sqlite3.Row objects to dictionaries
        return videos
        
    def search_videos(self, query: str, limit: int = 20):
        """
        Search for videos in the database by title
        
        :param query: Search query
        :param limit: Maximum number of results
        :return: list: List of matching videos
        """
        # This requires adding a new method to SQLiteStorage
        if hasattr(self.storage, 'search_videos'):
            videos = self.storage.search_videos(query, limit)  # TODO: Implement search_videos in SQLiteStorage
            return [dict(video) for video in videos] if videos else []
        else:
            print("Video search not implemented in storage")
            return []


class VideoManager:
    def __init__(self, storage: SQLiteStorage, downloader: MediaDownloader):
        """
        Initialize VideoManager
        
        :param storage: SQLiteStorage instance for data persistence
        :param downloader: MediaDownloader instance for fetching data
        """
        self.storage = storage
        self.downloader = downloader

    def process(self, video_id: str, force_update: bool = False) -> Optional[dict]:
        """
        Process a video: fetch info if needed, store in database, return data.
        Returns None if the video cannot be processed or found.
        
        :param video_id: YouTube video ID
        :param force_update: If True, force update regardless of last update time. Defaults to False.
        :return: dict: Video information or None
        """
        try:
            existing_video = self.storage.get_video(video_id)
            if existing_video:
                # Force update if requested OR if it needs an update based on time
                if force_update or self._needs_update(existing_video):
                    print(f"Updating video {video_id} ...")
                    return self.update_video(video_id)
                # Otherwise, return the existing data
                print(f"Video {video_id} exists. Returning cached data.")
                return dict(existing_video)

            # Video doesn't exist in DB, fetch it
            print(f"Video {video_id} not found in DB. Fetching...")
            video_info = self.downloader.get_video_info(video_id)
            if not video_info:
                print(f"Could not fetch info for video {video_id}")
                return None # Indicate failure to fetch

            # Ensure the channel exists before saving the video
            channel_id = video_info.get('channel_id')
            if channel_id and not self.storage.channel_exists(channel_id):
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
        
    def update_video(self, video_id: str) -> Optional[dict]:
        """
        Fetches fresh video information and updates the database.

        :param video_id: YouTube video ID
        :return: upddated video Info or None on failure
        """
        try:
            # Get fresh video data
            video_info = self.downloader.get_video_info(video_id)
            if not video_info:
                print(f"WARNING: Failed to fetch updated info for video {video_id}, downloader returned None.")
                # Update status to indicate fetch failure during update
                self.storage._update_video_status(video_id, 'update_fetch_failed')
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
            self.storage._update_video_status(video_id, 'update_processing_error')
            return None
        
    def _needs_update(self, existing_video: dict, days: int = 30) -> bool:
        """
        Determine if a video needs to be updated based on its last update time.
        Similar to ChannelManager._needs_update.

        :param existing_video: Existing video data from database (as dict).
        :param days: Number of days after which the data is considered stale.
        :return: bool: True if video needs update, False otherwise.
        """
        last_updated_str = existing_video.get('last_updated')
        if not last_updated_str:
            print(f"Video {existing_video.get('id')} missing 'last_updated' timestamp. Needs update.")
            return True # Needs update if timestamp is missing

        try:
            # Handle different possible formats (ISO with Z, ISO without Z, SQLite default)
            if 'T' in last_updated_str:
                if last_updated_str.endswith('Z'):
                    last_updated_str = last_updated_str.replace('Z', '+00:00')
                # Remove potential fractional seconds if present, as fromisoformat might struggle
                last_updated_str = re.sub(r'\\.\\d+', '', last_updated_str)
                last_updated = datetime.fromisoformat(last_updated_str)
            else:
                # Standard SQLite format "YYYY-MM-DD HH:MM:SS"
                last_updated = datetime.strptime(last_updated_str, '%Y-%m-%d %H:%M:%S')

            now = datetime.now()

            # Calculate time difference
            time_difference = now - last_updated
            update_threshold_seconds = days * 24 * 60 * 60

            needs_update = time_difference.total_seconds() > update_threshold_seconds
            if needs_update:
                 print(f"Video {existing_video.get('id')} needs update. Last updated: {last_updated_str} ({time_difference.days} days ago).")
            # else:
            #      print(f"Video {existing_video.get('id')} is up-to-date. Last updated: {last_updated_str} ({time_difference.days} days ago).")
            return needs_update

        except Exception as e:
            print(f"Error parsing timestamp '{last_updated_str}' for video {existing_video.get('id')}: {str(e)}. Assuming update needed.")
            # If we can't parse the timestamp, better to update
            return True



    def download_video(self, video_id: str, force_download: bool = False) -> Optional[str]:
            """
            Downloads a video, handling checks and database updates. Simplified flow.

            Steps:
            1. Check if video metadata exists in DB.
            2. If Yes: Check downloaded status. If downloaded & valid (and not forced), return path.
                    Otherwise, get channel info needed for download path.
            3. If No: Call process() to fetch video and channel info, saving to DB. If fails, return None.
                    Get channel info needed for download path from processed data.
            4. Perform the download using the downloader.
            5. Update DB on success.
            6. Return path on success, None otherwise.

            :param video_id: The ID of the video to download.
            :param force_download: If True, attempt download even if DB indicates
                                it's already downloaded. Defaults to False.
            :return: Absolute path to the downloaded file on success, None otherwise.
            """
            video_data_dict: Optional[dict] = None
            channel_id: Optional[str] = None
            channel_name: Optional[str] = None

            try:
                # 1. Check if video exists in DB
                existing_video_dict = self.storage.get_video(video_id)

                if existing_video_dict:
                    # 2. Video Exists in DB
                    video_data_dict = existing_video_dict
                    print(f"Video {video_id} found in database.")

                    # Check download status
                    if not force_download and video_data_dict.get('downloaded'):
                        file_path = video_data_dict.get('file_path')
                        if file_path and os.path.exists(file_path):
                            print(f"Video {video_id} already downloaded at: {file_path}")
                            return file_path
                        else:
                            print(f"Video {video_id} marked downloaded, but file missing ({file_path}). Proceeding.")

                    # Need channel info for download path
                    channel_id = video_data_dict.get('channel_id')
                    channel_data_row = self.storage.get_channel(channel_id)
                    channel_name = channel_data_row['name']

                else:
                    # 3. Video Does Not Exist in DB - Process it first
                    print(f"Video {video_id} not found in DB. Processing...")
                    processed_video_info = self.process(video_id) # Fetches video & ensures channel exists

                    if not processed_video_info:
                        print(f"Failed to process video {video_id}. Cannot download.")
                        return None

                    # Use the info returned by process()
                    video_data_dict = processed_video_info # Already a dict
                    channel_id = video_data_dict.get('channel_id')
                    # process() should have added channel_title to the video info dict
                    channel_name = video_data_dict.get('channel_title')

                    if not channel_id or not channel_name:
                        print(f"Error: Processed video {video_id} lacks channel_id or channel_title. Cannot download.")
                        return None

                # --- At this point, we should have channel_id and channel_name ---

                # 4. Perform Download
                print(f"Proceeding to download video {video_id} for channel '{channel_name}' ({channel_id})...")
                downloaded_file_path = self.downloader.download_video(video_id, channel_id, channel_name)

                # 5. Update DB / Handle Failure
                if downloaded_file_path:
                    update_success = self.storage._update_video_download_status(video_id, downloaded_file_path)
                    if not update_success:
                        print(f"CRITICAL WARNING: Video {video_id} downloaded to {downloaded_file_path} but failed to update database!")
                    # 6. Return path even if DB update fails, log warning above
                    return downloaded_file_path
                else:
                    print(f"Download failed for video {video_id}.")
                    # Optionally update status? e.g., self.storage._update_video_status(video_id, 'download_failed')
                    # 6. Return None on download failure
                    return None

            except Exception as e:
                print(f"An unexpected error occurred in VideoManager.download_video for {video_id}: {str(e)}")
                return None
            

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

    
    def process(self, playlist_id: str, force_update: bool = False) -> Optional[dict]:
        """
        Process a playlist: fetch info if needed, store in database, process its videos, and return data.
        Returns None if the playlist cannot be processed or found.

        :param playlist_id: YouTube playlist ID.
        :param force_update: If True, force update regardless of last update time. Defaults to False.
        :return: Playlist information dictionary or None.
        """
        try:
            existing_playlist = self.storage.get_playlist(playlist_id)
            if existing_playlist and not force_update and not self._needs_update(existing_playlist):
                print(f"Playlist {playlist_id} exists. Returning cached data.")
                return dict(existing_playlist)

            if existing_playlist and (force_update or self._needs_update(existing_playlist)):
                print(f"Updating playlist {playlist_id}...")
                # Fall through to fetch and update logic
            elif not existing_playlist:
                print(f"Playlist {playlist_id} not found in DB. Fetching...")

            # Fetch playlist info from YouTube
            playlist_info = self.downloader.get_playlist_info(playlist_id)
            if not playlist_info:
                print(f"Could not fetch info for playlist {playlist_id}")
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

            print(f"Starting processing videos from playlist {playlist_id}...")
            for video_entry in videos_in_playlist:
                video_id = video_entry.get('id')
                if not video_id:
                    continue

                video_details = self.video_manager.process(video_id, force_update=force_update)

                if video_details:
                    processed_video_count += 1
                    # Link this video to the current playlist
                    # The `save_video` in `VideoManager` does NOT update playlist_id on conflict.
                    if self.storage._update_video_playlist_id(video_id, playlist_id):
                        linked_video_count +=1
                else:
                    print(f"Failed to process video {video_id} from playlist {playlist_id}.")
            
            print(f"Processed {processed_video_count} videos for playlist {playlist_id}. Linked {linked_video_count} videos.")

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