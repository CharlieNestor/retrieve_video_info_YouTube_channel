import os
from dotenv import load_dotenv

# Low-level "worker" components
from parser import InputParser
from storage import SQLiteStorage
from downloader import MediaDownloader

# High-level "manager" components
from channel_manager import ChannelManager
from video_manager import VideoManager
from playlist_manager import PlaylistManager
from library_manager import LibraryManager

# Load environment variables from a .env file
load_dotenv()

class YouTubeClient:
    """
    The main entry point and coordinator for all YouTube data operations.

    This class initializes and wires together all the necessary components,
    including the parser, storage, downloader, and the specialized managers
    for channels, videos, and playlists. It acts as a facade, providing a
    simple interface to the user for processing any YouTube URL.
    """

    def __init__(self, database_path: str = None, download_dir: str = None):
        """
        Initializes the client and all its components.

        :param database_path: The absolute path to the SQLite database file.
                            Defaults to 'youtube.db' inside the download directory.
        :param download_dir: The directory for storing downloaded media.
                            Defaults to the path specified in the DOWNLOAD_DIR
                            environment variable.
        """
        # 1. Determine and validate paths
        if download_dir is None:
            print("WARNING: No download directory specified via parameter.")
            download_dir = os.getenv('DOWNLOAD_DIR')
            if download_dir is None: # If not provided by parameter or env var, default to system Downloads
                print("WARNING: DOWNLOAD_DIR environment variable not found. Defaulting to system Downloads folder.")
                download_dir = os.path.join(os.path.expanduser('~'), 'Downloads')
        
        # Ensure the download directory exists
        os.makedirs(download_dir, exist_ok=True)

        if database_path is None:
            print("WARNING: No database path specified via parameter. Defaulting to 'youtube.db'.")
            database_path = os.path.join(download_dir, 'youtube.db')

        print(f"Initializing YouTubeClient with DB: {database_path} and Downloads: {download_dir}")

        # 2. Initialize low-level "worker" components
        self.parser = InputParser()
        self.storage = SQLiteStorage(database_path)
        self.downloader = MediaDownloader(download_dir)

        # 3. Initialize high-level "manager" components by injecting dependencies
        self.channel_manager = ChannelManager(self.storage, self.downloader)
        self.video_manager = VideoManager(self.storage, self.downloader, self.channel_manager)
        self.playlist_manager = PlaylistManager(self.storage, self.downloader, self.video_manager)
        self.library_manager = LibraryManager(storage=self.storage, download_dir=download_dir, video_manager=self.video_manager, downloader=self.downloader)

        # 4. Sync library on startup
        #self.library_manager.sync_library()

    def process_url(self, url: str, force_update: bool = False) -> dict:
        """
        Processes any given YouTube URL (channel, video, playlist, or short).

        It parses the URL to determine the entity type and then delegates the
        processing to the appropriate manager. It also handles associated
        entities, such as a playlist ID found in a video URL.

        :param url: The YouTube URL to process.
        :param force_update: If True, forces a fresh fetch of the data from YouTube,
                            ignoring any cached data. Defaults to False.
        :return: A dictionary where keys are entity types ('channel', 'video', 'playlist')
                 and values are the processed data for that entity. If an entity is not
                 present in the URL, its key will not be in the dictionary.
                 Raises a ValueError for an unsupported URL.
        """
        print(f"YouTubeClient processing URL: {url}")
        try:
            # Use the parser to identify what the URL points to
            entity_type, entity_id, associated_video_id, associated_playlist_id = self.parser.parse_url(url)
            
            processed_entities = {}

            # Delegate to the appropriate manager based on the entity type
            if entity_type == 'channel':
                processed_entities['channel'] = self.channel_manager.process(entity_id, force_update=force_update)

            elif entity_type == 'video' or entity_type == 'short':
                processed_entities['video'] = self.video_manager.process(video_id=entity_id, force_update=force_update)
                
                # If the video URL also contained a playlist, process the playlist as well
                if associated_playlist_id:
                    print(f"Processing associated playlist {associated_playlist_id} from video URL...")
                    processed_entities['playlist'] = self.playlist_manager.process(playlist_id=associated_playlist_id, force_update=force_update)

            elif entity_type == 'playlist':
                processed_entities['playlist'] = self.playlist_manager.process(playlist_id=entity_id, force_update=force_update)

                # If the playlist URL also contained a specific video, process that video as well
                if associated_video_id:
                    print(f"Processing associated video {associated_video_id} from playlist URL...")
                    processed_entities['video'] = self.video_manager.process(video_id=associated_video_id, force_update=force_update)
            
            else:
                raise ValueError(f"Unknown or unsupported entity type returned by parser: {entity_type}")

            return processed_entities

        except ValueError as e:
            print(f"Error processing URL: {e}")
            raise
        except Exception as e:
            print(f"An unexpected error occurred in the client: {e}")
            raise

    def close_connection(self):
        """
        Closes the database connection gracefully.
        """
        print("Closing database connection.")
        self.storage.close()
