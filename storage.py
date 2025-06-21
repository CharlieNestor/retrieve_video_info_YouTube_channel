import sqlite3
import json
from typing import List, Dict, Union, Any

class SQLiteStorage:
    """
    A storage class for managing YouTube video metadata in a SQLite database.

    Handles storage operations for channels, videos, playlists, and related metadata
    with support for CRUD operations and relationship management.
    """
    def __init__(self, db_path: str):
        """
        Initialize database connection and create schema if needed

        :param db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        self.conn = None    # TODO: Implement better connection management
        self._connect()
        self._create_schema()


    # TODO: Implement context manager methods to allow using SQLiteStorage with 'with' statement
    def __enter__(self):
        """Allow using SQLiteStorage with 'with' statement"""
        if self.conn is None:
            self._connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Automatically close connection when exiting context"""
        self.close()
        # Don't suppress exceptions
        return False

    #####################
    
    def _connect(self):
        """
        Establish connection to SQLite database with foreign key support.
        Sets row_factory to sqlite3.Row for dictionary-like access to results.
        """
        self.conn = sqlite3.connect(self.db_path)
        # Enable foreign key constraints
        self.conn.execute("PRAGMA foreign_keys = ON")
        # Return dictionaries instead of tuples
        self.conn.row_factory = sqlite3.Row

    def _create_schema(self):
        """
        Create database schema if a current table doesn't exist.
        Creates tables for channels, videos, playlists, tags, and their relationships 
        with appropriate foreign key constraints.
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
            FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
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
                             
        -- Playlist-video relations
        CREATE TABLE playlist_videos (
            playlist_id TEXT,
            video_id TEXT,
            position INTEGER, -- Optional: track position in playlist
            PRIMARY KEY (playlist_id, video_id),
            FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
            FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
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
        print("ATTENTION: Database schema CREATED successfully")

    def _check_tables_exist(self) -> bool:
        """
        Check if all required tables exist in the database.

        :return bool: True if all the tables exist, False if any are missing
        """
        cursor = self.conn.cursor()
        required_tables = ['entity_types', 'channels', 'videos', 'playlists', 
                        'playlist_videos', 'tags', 'video_tags', 'timestamps']
        
        for table in required_tables:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            )
            if not cursor.fetchone():
                return False
        return True
    

    ##### CHANNEL OPERATIONS #####

    def save_channel(self, channel_data: dict):
        """
        Insert or update channel information into the database.
        Uses SQlite UPSERT syntax to handle insertions (if ID does not exist) and
        updates (if ID already exists) in a single query.

        :param channel_data: Dict containing channel information
        """
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
            -- insertion
            INSERT INTO channels (
                id, name, description, subscriber_count, video_count, 
                thumbnail_url, content_breakdown, 
                created_at, 
                last_updated
            ) VALUES (?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            -- update
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

    def get_channel(self, channel_id: str) -> Union[Dict, None]:
        """
        Get channel by ID

        :param channel_id: The unique identifier of the channel
        :return: Dictionary containing channel information or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM channels WHERE id = ?", (channel_id,))
        row = cursor.fetchone()
        return dict(row) if row else None # Convert Row to dict if found
    
    def _channel_exists(self, channel_id: str) -> bool:
        """
        Check if channel exists in database

        :param channel_id: The unique identifier of the channel
        :return: True if the the query ID actually exist, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM channels WHERE id = ?", (channel_id,))
        return cursor.fetchone() is not None
    
    def list_channels(self, limit: int = None, sort_by: str = "name") -> List[Dict]:
        """
        List channels with pagination and sorting

        :param limit: The max number of channels to be returned
        :param sort_by: The sorting criteria for the channel shown. Valid values 'id', 'name'
        :return: List of dictionaries containing channel id and name
        """
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
        
    def delete_channel(self, channel_id: str):
        """
        Delete channel from the database.
        Due to ON DELETE CASCADE constraint, all related videos will be automatically deleted.

        :param channel_id: The unique identifier of the channel to be deleted
        """
        # Check if the channel exists first
        if not self._channel_exists(channel_id):
            raise ValueError(f"WARNING: Channel ID {channel_id} does not exist in the database.")
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
        self.conn.commit()

    
    ###### VIDEO OPERATIONS #####

    def save_video(self, video_data: dict):
        """
        Insert or update video information into the database.
        Uses SQLite UPSERT syntax to handle insertions (if ID does not exist) and
        updates (if ID already exists) in a single query.

        :param video_data: Dict containing video information
        """
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
                id, title, description, channel_id, channel_title, 
                published_at, duration, view_count, like_count,
                thumbnail_url, is_short, is_live, status, 
                file_path, transcript_path, downloaded, download_date,
                last_updated
            ) VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,    -- 13 fields from video_data
                ?, ?, ?, ?,                               -- 4 fields: file_path, transcript_path, downloaded, download_date
                CURRENT_TIMESTAMP                         -- last_updated
            )
            ON CONFLICT(id) DO UPDATE SET
                title = excluded.title,
                description = excluded.description,
                -- channel_id = excluded.channel_id, -- channel_id should not change for an existing video ID.
                channel_title = excluded.channel_title,
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
        """
        params = (
            video_data['id'],
            video_data['title'],
            video_data.get('description'),
            video_data['channel_id'],
            video_data.get('channel_title'),
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
        
    def get_video(self, video_id: str) -> Union[Dict, None]:
        """
        Get video by ID.

        :param video_id: The unique identifier of the video
        :return: Dictionary containing video information or None if not found
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = cursor.fetchone()
        return dict(row) if row else None # Convert Row to dict if found
    
    def _video_exists(self, video_id: str) -> bool:
        """
        Check if video exists in database.

        :param video_id: The unique identifier of the video
        :return: True if the video exists, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM videos WHERE id = ?", (video_id,))
        return cursor.fetchone() is not None
    
    def list_channel_videos(self, channel_id: str, limit: int = None, sort_by: str= "published_at") -> List[Dict]:
        """
        Get videos for a specific channel with optional pagination and sorting.

        :param channel_id: The unique identifier of the channel
        :param limit: The maximum number of videos to return
        :param sort_by: The sorting criteria for the videos shown. Valid values 'title', 'published_at'
        :return: List of dictionaries containing video id and title
        """
        if not self._channel_exists(channel_id):
            print(f"WARNING: Channel with ID {channel_id} does not exist.")
            return []
        
        # Validate sort_by parameter
        if sort_by not in ['title', 'published_at']:
            print(f"WARNING: Invalid sort_by column: {sort_by}. Defaulting to published_at.")
            sort_by = 'published_at'
        
        cursor = self.conn.cursor()

        # Build the query with optional limit and sorting
        query = "SELECT id, title FROM videos WHERE channel_id = ?"

        # Apply sorting based on the validated sort_by parameter
        if sort_by == 'published_at':
            query += " ORDER BY published_at DESC"  # Most recent videos first
        else:  # sort_by == 'title'
            query += " ORDER BY title ASC"  # Alphabetical order
        
        # Apply limit if provided
        if limit:
            query += f" LIMIT {limit}"
        try:
            cursor.execute(query, (channel_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except Exception as e:
            print(f"Error getting channel videos: {e}")
            return []
        
    def _update_video_status(self, video_id: str, status: str) -> bool:
        """
        Update the status of a video in the database.
        This method is used to change the availability status of a video, i.e., marking it as 'available' or 'unavailable'.
        A video might be marked as unavailable if it has been removed from YouTube or is no longer accessible.

        :param video_id: The unique identifier of the video
        :param status: The new status to set for the video (e.g., 'available', 'unavailable')
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
        This method is used to mark a video as downloaded and store the file path of the downloaded video.
        It can happen for a video to be already downloaded in the storage, hence once we save it in the database,
        we also need to update the download status and file path manually with this specific method.

        :param video_id: ID of the video to update.
        :param file_path: Absolute path to the downloaded video file.
        :return: True if update was successful, False otherwise.
        """
        # Check if the video exists first
        if not self._video_exists(video_id):
            print(f"WARNING: Video ID {video_id} does not exist in the database.")
            return False
        # Validate file_path
        if not file_path:
            print(f"WARNING: file_path cannot be empty when updating download status for video {video_id}.")
            return False
        
        # Update the video record with the file path and set downloaded to 1
        # Also set download_date to CURRENT_TIMESTAMP
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
        
        
    def delete_video(self, video_id: str):
        """
        Delete video from database.

        :param video_id: The unique identifier of the video to be deleted
        """
        # Check if the video exists first
        if not self._video_exists(video_id):
            raise ValueError("WARNING: Video ID {video_id} does not exist in the database.")
        
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        self.conn.commit()


    ###### TAGS OPERATIONS #####

    # Tags are used to categorize videos, allowing for easier searching and filtering.
    # Tags are defined by the author of the video and can be associated with multiple videos.


    def save_video_tags(self, video_id: str, tags: List[str]) -> bool:
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
                # No new tags were provided as input.
                print(f"WARNING: No new tags provided for video {video_id}.")


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
        
    
    def list_tags(self, limit: int = None, sort_by: str = "name") -> List[Dict[str, Any]]:
        """
        Lists all unique tag names from the 'tags' table.

        :param limit: Optional. The maximum number of tags to return.
        :param sort_by: The column to sort by. Valid values are 'name' or 'frequency'.
        :return: A list of dictionaries, each containing 'name' and 'frequency' of the tag.
        """
        cursor = self.conn.cursor()
        # Basic validation for sort_by to prevent SQL injection if it were user-facing without sanitization
        allowed_sort_columns = ["name"]     # can be extended with more columns if needed
        if sort_by not in allowed_sort_columns:
            sort_by = "name" # Default to a safe column

        # Join with video_tags to count occurrences
        query = """
            SELECT t.name, COUNT(vt.video_id) AS frequency
            FROM tags t
            LEFT JOIN video_tags vt ON t.id = vt.tag_id
            GROUP BY t.name
            ORDER BY 
        """

        # Add the appropriate ORDER BY clause based on sort_by
        if sort_by == "frequency":
            query += "frequency DESC, t.name ASC"
        else:  # sort_by == "name"
            query += "t.name ASC"

        params = []

        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except sqlite3.Error as e:
            print(f"Database error listing tags: {e}")
            return []
        
    
    def get_tags_video(self, video_id: str) -> List[str]:
        """
        Retrieves all tag names associated with a specific video.

        :param video_id: The ID of the video.
        :return: A list of tag names for the video, or an empty list if none are found.
        """
        # First check if the video exists
        if not self._video_exists(video_id):
            print(f"WARNING: Video with ID {video_id} not found. Cannot retrieve tags.")
            return []
        
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
        
    
    def get_tags_channel(self, channel_id: str, limit: int = None, min_video_count: int = 1) -> List[Dict[str, Any]]:
        """
        Retrieves all unique tags used by videos belonging to a specific channel,
        along with the count of videos in that channel using each tag.

        :param channel_id: The ID of the channel.
        :param limit: Optional. The maximum number of unique tags to return (ordered by most used).
        :param min_video_count: Minimum number of videos a tag must be associated with in this channel to be included.
        :return: A list of dictionaries, each containing 'tag_name' and 'video_count',
                or an empty list if no relevant tags are found.
        """
        # First check if the channel exists
        if not self._channel_exists(channel_id):
            print(f"WARNING: Channel with ID {channel_id} does not exist. Cannot retrieve tags.")
            return []

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
        
    
    ###### TIMESTAMPS OPERATIONS #####

    # Timestamps are used to mark specific points in a video, such as chapters or highlights.
    # Timestamps are defined by the author of the video and can be used to navigate to specific parts of the video.


    def save_video_timestamps(self, video_id: str, timestamps: List[Dict[str, Any]]) -> bool:
        """
        Saves video chapters/timestamps to the database.
        Deletes existing timestamps for the video before inserting new ones.

        :param video_id: The ID of the video.
        :param timestamps: A list of dictionaries, each with 'start_time' (int) and 'title' (str).
        :return: True if saving was successful, False otherwise.
        """
        # Check if the video exists first
        if not self._video_exists(video_id):
            print(f"WARNING: Video with ID {video_id} not found. Cannot save timestamps.")
            return False
    
        cursor = self.conn.cursor()
        
        try:
            # 1. Delete existing timestamps for this video
            cursor.execute("DELETE FROM timestamps WHERE video_id = ?", (video_id,))

            # Handle cases where timestamps might be None or empty
            if not timestamps: # Checks for None or empty list
                print(f"WARNING: No timestamps provided or found for video {video_id}. Existing timestamps (if any) cleared.")
                self.conn.commit() # Commit the delete operation
                return True
            
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
        
    
    def get_video_timestamps(self, video_id: str) -> List[Dict[str, Any]]:
        """
        Retrieves all timestamps (chapters) for a specific video.

        :param video_id: The ID of the video.
        :return: A list of dictionaries, each representing a timestamp 
                 (e.g., {'time_seconds': 0, 'description': 'Intro'}).
                 Returns an empty list if no timestamps are found or video doesn't exist.
        """
        # First check if the video exists
        if not self._video_exists(video_id):
            print(f"WARNING: Video with ID {video_id} does not exist. Cannot retrieve timestamps.")
            return []
        
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
        

    ##### PLAYLIST OPERATIONS #####


    def save_playlist(self, playlist_data: dict) -> bool:
        """
        Insert or update playlist information into the database.
        Uses SQLite UPSERT syntax to handle insertions (if ID does not exist) and
        updates (if ID already exists) in a single query.

        :param playlist_data: Dict containing playlist information
        :return: True if the playlist was saved successfully, False otherwise.
        """
        cursor = self.conn.cursor()

        # Ensure channel_id exists before saving playlist
        channel_id = playlist_data.get('channel_id')
        if not channel_id:
            print("ERROR: Cannot save playlist without a channel_id")
            return False
        
        # Check if the channel exists
        if not self._channel_exists(channel_id):
            print(f"WARNING: Channel ID {channel_id} does not exist. Cannot save playlist.")
            return False
        
        try:
            # 1. Save/update playlist metadata
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
            
            # 2. Update playlist-video associations if videos are provided
            if 'videos' in playlist_data and playlist_data['videos']:
                stats = self._associate_videos_with_playlist(
                    playlist_data['id'],
                    playlist_data['videos']
                )
                
                updates_summary = []
                if stats['inserted'] > 0:
                    updates_summary.append(f"{stats['inserted']} videos added")
                if stats['updated'] > 0:
                    updates_summary.append(f"{stats['updated']} positions updated")
                if stats['removed'] > 0:
                    updates_summary.append(f"{stats['removed']} videos removed")
                    
                if updates_summary:
                    print(f"Playlist '{playlist_data['title']}' updated: {', '.join(updates_summary)}")
                else:
                    print(f"No changes needed for playlist '{playlist_data['title']}'")

            return True  # Indicate success
        
        except Exception as e:
            print(f"Error saving playlist {playlist_data['id']}: {e}")
            self.conn.rollback()
            return False  # Indicate failure
    
    def _associate_videos_with_playlist(self, playlist_id: str, videos: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Associate multiple videos with a playlist, handling position information.
        This is an optimized bulk operation for playlist-video relationships.
        
        :param playlist_id: The playlist ID
        :param videos: List of video dictionaries containing at least 'id'
        :return: Dict with counts of operations performed: {'updated': X, 'inserted': Y, 'removed': Z}
        """
        if not playlist_id or not videos:
            return {'updated': 0, 'inserted': 0, 'removed': 0}
            
        cursor = self.conn.cursor()
        try:
            # Begin transaction for performance
            cursor.execute("BEGIN TRANSACTION")
            
            # Get existing video associations for this playlist
            cursor.execute("SELECT video_id, position FROM playlist_videos WHERE playlist_id = ?", (playlist_id,))
            existing_videos = {row['video_id']: row['position'] for row in cursor.fetchall()}
            
            # Track new video IDs for insertion
            new_video_ids = set()
            stats = {'updated': 0, 'inserted': 0, 'removed': 0}
            
            # Process each video in the playlist
            for position, video in enumerate(videos):
                video_id = video.get('id')
                if not video_id:
                    continue
                    
                new_video_ids.add(video_id)
                
                # Check if this video exists in the playlist
                if video_id in existing_videos:
                    # Only update if position has changed
                    if existing_videos[video_id] != position:
                        cursor.execute("""
                            UPDATE playlist_videos 
                            SET position = ? 
                            WHERE playlist_id = ? AND video_id = ?
                        """, (position, playlist_id, video_id))
                        stats['updated'] += 1
                else:
                    # Insert new association
                    cursor.execute("""
                        INSERT INTO playlist_videos (playlist_id, video_id, position)
                        VALUES (?, ?, ?)
                    """, (playlist_id, video_id, position))
                    stats['inserted'] += 1
            
            # Remove associations for videos no longer in the playlist
            videos_to_remove = set(existing_videos.keys()) - new_video_ids
            if videos_to_remove:
                placeholders = ','.join(['?'] * len(videos_to_remove))
                cursor.execute(f"""
                    DELETE FROM playlist_videos 
                    WHERE playlist_id = ? AND video_id IN ({placeholders})
                """, (playlist_id, *videos_to_remove))
                stats['removed'] = len(videos_to_remove)
                
            # Commit all changes
            cursor.execute("COMMIT")
            return stats
            
        except Exception as e:
            cursor.execute("ROLLBACK")
            print(f"Error associating videos with playlist {playlist_id}: {e}")
            return {'updated': 0, 'inserted': 0, 'removed': 0}
        
        
    def get_playlist(self, playlist_id: str) -> Union[Dict, None]:
        """
        Get playlist by ID
        :param playlist_id: The unique identifier of the playlist
        :return: Dictionary containing playlist information or None if not found
        """
        # Check if the playlist exists first
        if not self._playlist_exists(playlist_id):
            print(f"WARNING: Playlist with ID {playlist_id} does not exist.")
            return None
        # Fetch playlist details from the database
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM playlists WHERE id = ?", (playlist_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def _playlist_exists(self, playlist_id: str) -> bool:
        """
        Check if playlist exists in database

        :param playlist_id: The unique identifier of the playlist
        :return: True if the playlist exists, False otherwise
        """
        cursor = self.conn.cursor()
        cursor.execute("SELECT 1 FROM playlists WHERE id = ?", (playlist_id,))
        return cursor.fetchone() is not None
    

    def list_playlists(self, limit: int = None, sort_by: str = "title", channel_id: str = None) -> List[dict]:
        """
        Lists playlists from the database.

        :param limit: Optional. The maximum number of playlists to return.
        :param sort_by: The column to sort by. Valid values are 'title', 'video_count', 'channel_title'. Defaults to 'title'.
        :param channel_id: Optional. Filter playlists by a specific channel ID.
        :return: A list of playlist dictionaries (id, title, channel_id, video_count, modified_date, last_updated).
        """
        # Validate channel_id if provided
        if channel_id and not self._channel_exists(channel_id):
            print(f"WARNING: Channel with ID {channel_id} does not exist. Cannot list playlists for this channel.")
            return []
        
        cursor = self.conn.cursor()
        
        allowed_sort_columns = ["title", "channel_id", "video_count"]
        if sort_by not in allowed_sort_columns:
            print(f"WARNING: Invalid sort_by column '{sort_by}' for list_playlists. Defaulting to 'title'.")
            sort_by = "title"

        db_sort_column = "p.title" # Default
        if sort_by == "title":
            db_sort_column = "p.title"
        elif sort_by == "video_count":
            db_sort_column = "p.video_count"
        elif sort_by == "channel_title":
            db_sort_column = "c.name"

        query = "SELECT p.id, p.title, c.name AS channel_title, p.video_count FROM playlists p JOIN channels c ON p.channel_id = c.id"
        params = []

        if channel_id:
            query += " WHERE channel_id = ?"
            params.append(channel_id)
        
        query += f" ORDER BY {db_sort_column} ASC"  # Default to ascending order}"

        # Apply limit if provided
        if limit is not None and limit > 0:
            query += " LIMIT ?"
            params.append(limit)
        
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except sqlite3.Error as e:
            print(f"Database error listing playlists: {e}")
            return []
        
    
    def get_playlist_videos(self, playlist_id: str, limit: int = None, sort_by: str = "position") -> List[dict]:
        """
        Get videos and associated information with a specific playlist from the database.

        :param playlist_id: The ID of the playlist.
        :param limit: Maximum number of videos to return.
        :param sort_by: Column to sort videos by. Valid values are 'position', 'published_at', 'title'.
        :return: A list of video dictionaries.
        """
        # Check if the playlist exists first
        if not self._playlist_exists(playlist_id):
            print(f"WARNING: Playlist with ID {playlist_id} does not exist.")
            return []
        
        cursor = self.conn.cursor()
        
        essential_fields = ['v.id', 'v.title', 'v.published_at', 'pv.position']
        select_columns = ", ".join(essential_fields)

        allowed_sort_columns = ['position', 'published_at', 'title'] 
        if sort_by not in allowed_sort_columns:
            print(f"WARNING: Invalid sort_by column '{sort_by}' for get_playlist_videos. It must be one of {allowed_sort_columns}. Defaulting to 'published_at'.")
            sort_by = 'published_at'

        # Map allowed_sort_columns to actual DB columns with table prefix
        sort_column_map = {
            'position': 'pv.position',
            'published_at': 'v.published_at',
            'title': 'v.title',
        }
        db_sort_column = sort_column_map.get(sort_by)

        # Query using the junction table
        query = f"""
            SELECT {select_columns} 
            FROM videos v
            JOIN playlist_videos pv ON v.id = pv.video_id
            WHERE pv.playlist_id = ?
            ORDER BY {db_sort_column} ASC
        """
        
        params = [playlist_id]
        
        if limit is not None:
            query += " LIMIT ?"
            params.append(limit)
        
        try:
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(row) for row in rows] if rows else []
        except sqlite3.Error as e:
            print(f"Database error in get_videos_by_playlist for playlist {playlist_id}: {e}")
            return []
        

    def close(self):
        """
        Close the database connection
        """
        if self.conn:
            self.conn.close()





