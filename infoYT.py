import re
import os
import json
import pytz
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from logging_config import logger
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mongo_operations import MongoOperations
from typing import List, Dict, Any, Tuple, Union


# Load the environment variables
load_dotenv()


# YouTube API setup
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'
DEVELOPER_KEY = os.getenv('YOUTUBE_API_KEY')


### UTILITY FUNCTIONS

class QuotaExceededException(Exception):
    pass


def to_rfc3339_format(date: datetime) -> str:
    """
    convert a datetime object to an RFC 3339 formatted date-time string.
    :param date: datetime object
    :return: RFC 3339 formatted date-time string
    """
    if date.tzinfo is None:
        date = date.replace(tzinfo=pytz.UTC)
    return date.isoformat()


def extract_video_id(url: str) -> Union[str, None]:
    """
    extract the video ID from a YouTube URL.
    :param url: YouTube video URL
    :return: video ID
    """
    video_id_match = re.search(r'(?:v=|youtu\.be/|/v/|/embed/|/shorts/)([^\s&?]+)', url)
    if video_id_match:
        return video_id_match.group(1)
    return None


def extract_channel_id(url: str) -> Union[str, None]:
    """
    extract the channel ID or username from a YouTube URL.
    :param url: YouTube URL
    :return: channel ID
    """
    channel_id_match = re.search(r'(?:youtube\.com/(?:c/|channel/|user/|@))([^/?&]+)', url)
    if channel_id_match:
        return channel_id_match.group(1)
    return None
    

def extract_timestamps(description:str) -> Dict[str, str]:
    """
    extract timestamps and their corresponding subtitles from the video description, if present.
    :param description: video description
    :return: dictionary of timestamps and subtitles
    """
    timestamp_pattern = re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?)\s*([^\n]*)')    # matches MM:SS or HH:MM:SS followed by subtitles
    matches = timestamp_pattern.findall(description)
    timestamps = {match[0]: match[1].strip() for match in matches}
    return timestamps if timestamps else None


def sort_videos_by_date(videos_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    sort the videos dictionary by 'published_at' field in decreasing order (most recent first).
    :param videos_dict: dictionary of video data
    :return: sorted dictionary of video data
    """
    # Convert the dictionary to a list of tuples (video_id, video_data)
    video_items = list(videos_dict.items())
    
    # Sort the list based on the 'published_at' field
    sorted_items = sorted(
        video_items,
        key=lambda x: datetime.strptime(x[1]['published_at'], '%Y-%m-%dT%H:%M:%SZ'),
        reverse=True
    )
    sorted_dict = dict(sorted_items)
    
    return sorted_dict


### MAIN CLASS

class InfoYT():
    """
    This class retrieves information about a YouTube channel and its videos.
    """

    def __init__(self, url: str, data_source: str = "Local JSON", mongo_client = None) -> None:
        """
        Initialize the InfoYT object with a YouTube channel URL.
        :param url: YouTube channel URL
        :param data_source: Preferred data source ("MongoDB" or "Local JSON")
        """

        # Initialize YouTube API client
        self.youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=DEVELOPER_KEY)
        # Initialize MongoDB client
        self.mongo = None
        self.db_connected = False
        if data_source == "MongoDB":
            if mongo_client:
                self.mongo = mongo_client
                self.db_connected = self.verify_mongo_connection()
            else:
                self.mongo = MongoOperations()
                self.db_connected = self.mongo.connect()
            logger.info(f"Initial MongoDB connection status: {self.db_connected}")
        
        # Get channel ID and username from URL
        try:
            # Get channel info from URL
            self.channel_info = self.get_channel_info(url)
            self.channel_id = self.channel_info['id']
            self.channel_username = self.channel_info['title']
            self.num_videos = int(self.channel_info['video_count'])
            self.channel_description = self.channel_info['description']
            self.channel_keywords = self.channel_info['keywords']
            self.channel_thumbnails = self.channel_info['thumbnails']
            self.subscriber_count = int(self.channel_info['subscriber_count'])
            self.view_count = int(self.channel_info['view_count'])

            self.all_videos = {}
            self.most_recent_date = None
            self.oldest_date = None

            # Check if the connection to the database was successful
            if data_source == "MongoDB" and self.db_connected:
                self.load_from_db()
            else:
                self.load_from_json()

            # If no data is found, initialize a new channel
            if not self.all_videos:
                self.initialize_new_channel()
            
            # Print overall channel info
            self.get_info()
            logger.info(f"Initialized InfoYT for channel: {self.channel_username}, Data source: {data_source}, Videos: {len(self.all_videos)}")
        except Exception as e:
            logger.error(f"Error initializing InfoYT: {str(e)}", exc_info=True)
            raise


    ### INITIALIZATION METHODS

    def get_channel_id_from_video(self, video_id: str) -> str:
        """
        Function to get the channel ID from a video ID.
        :param video_id: YouTube video ID
        :return: channel ID
        """
        try:
            request = self.youtube.videos().list(
                part="snippet",
                id=video_id
            )
            response = request.execute()
            logger.info(f"API call: youtube.videos().list for video ID: {video_id}")

            if 'items' in response and len(response['items']) > 0:
                return response['items'][0]['snippet']['channelId']
            else:
                raise ValueError("Video not found")
        except Exception as e:
            logger.error(f"Error in get_channel_id_from_video: {str(e)}", exc_info=True)
            raise ValueError("Error in get_channel_id_from_video")
        
        
    def get_channel_id_from_username(self, username: str) -> str:
        """
        Search for a YouTube channel ID using the channel username.
        """
        try:
            request = self.youtube.search().list(
                part="snippet",
                type="channel",
                q=username,
                maxResults=1
            )
            response = request.execute()
            logger.info(f"API call: youtube.search().list for username: {username}")

            if 'items' in response and len(response['items']) > 0:
                return response['items'][0]['snippet']['channelId']
            else:
                raise ValueError(f"Channel not found for username: {username}")
        except Exception as e:
            logger.error(f"Error in get_channel_id_from_username: {str(e)}", exc_info=True)
            raise ValueError("Error in get_channel_id_from_username")
        
    
    def get_channel_info(self, url: str) -> Dict[str, Any]:
        """
        Function to obtain information about a YouTube channel.
        :param url: YouTube channel URL
        :return: dictionary of channel information
        """
        # Extract channel username or ID from URL
        channel_identifier = extract_channel_id(url)
        # We did not find any identifier in the URL
        if not channel_identifier:
            # Check if it's a video URL
            video_id = extract_video_id(url)
            if video_id:
                channel_id = self.get_channel_id_from_video(video_id)
            else:
                raise ValueError("Invalid YouTube URL")
        else:
            # We have a channel identifier and we are going to retrieve the channel ID from it
            channel_id = self.get_channel_id_from_username(channel_identifier)
            
        print(f"Channel ID: {channel_id}")

        try:
            request = self.youtube.channels().list(
                part="snippet,statistics",
                id=channel_id
            )
            response = request.execute()
            logger.info(f"API call: youtube.channels().list for channel ID: {channel_id}")

            if 'items' in response and len(response['items']) > 0:
                channel_info = response['items'][0]
                snippet = channel_info['snippet']
                statistics = channel_info['statistics']

                channel_data = {
                    'id': channel_id,
                    'title': snippet.get('title', None),
                    'description': snippet.get('description', None),
                    'keywords': snippet.get('keywords', None),
                    'thumbnails': snippet.get('thumbnails', None),
                    'video_count': statistics.get('videoCount', None),
                    'view_count': statistics.get('viewCount', None),
                    'subscriber_count': statistics.get('subscriberCount', None),
                }

                return channel_data
            else:
                raise ValueError("Channel not found")

        except Exception as e:
            logger.error(f"Error in get_channel_info: {str(e)}", exc_info=True)
            raise ValueError("Error in get_channel_info")
        

    def check_history(self, verbose=True) -> bool:
        """
        Check if a file with the channel's videos already exists in the Channel_Videos folder.
        If the folder doesn't exist, we will create it.
        """
        filename = f"{self.channel_username.replace(' ', '')}_videos.json"
        folder_path = 'Channel_Videos'
        file_path = os.path.join(folder_path, filename)

        if os.path.exists(folder_path):
            if os.path.isfile(file_path):
                if verbose:
                    print(f"We already have history record for this channel in the file {filename}.")
                    logger.info(f"History record found for channel: {self.channel_username}")
                return True
            else:
                if verbose:
                    print(f"The file {filename} doesn't exist yet in the {folder_path}/ folder. \nThere is no history record for this channel.")
                    logger.info(f"No history record found for channel: {self.channel_username}")
                return False
        else:
            # Create the folder if it doesn't exist
            os.makedirs(folder_path)
            print(f"The folder '{folder_path}' has been created. No files were previously stored.")
            return False
        

    def load_from_json(self) -> None:
        """
        Load channel data from local JSON file.
        """
        if self.check_history(verbose=True):
            filename = self.channel_username.replace(' ', '') + '_videos.json'
            folder_path = 'Channel_Videos'
            file_path = os.path.join(folder_path, filename)
            with open(file_path, 'r') as f:
                self.all_videos = json.load(f)
            print(f"Video data has been loaded from {file_path}")
            logger.info(f"Loaded {len(self.all_videos)} videos from JSON for channel: {self.channel_username}")
        else:
            logger.info(f"No existing JSON data found for channel: {self.channel_username}")


    def load_from_db(self) -> None:
        """
        Load channel data from MongoDB.
        """
        if self.db_connected:
            channel_data = self.mongo.get_channel(self.channel_username)
            if channel_data:
                db_videos = self.mongo.get_all_videos(self.channel_username)
                for video in db_videos:
                    video_id = video.pop('_id')
                    self.all_videos[video_id] = video
                print(f"Loaded {len(self.all_videos)} videos from the database.")
                logger.info(f"Loaded {len(self.all_videos)} videos from MongoDB for channel: {self.channel_username}")
            else:
                logger.info(f"No data found in MongoDB for channel: {self.channel_username}")


    def initialize_new_channel(self) -> None:
        """
        Initialize data for a new channel with no existing record.
        If the channel has 500 or fewer videos, retrieve all video IDs.
        Otherwise, set a flag for lazy loading.
        """
        if self.num_videos <= 500:
            self.all_video_ids = self.get_all_video_ids()
        else:
            self.lazy_load = True
            self.all_video_ids = None       # Will be populated later as needed

        self.update_dates()  # Update dates based on any existing data
        self.sync_channel_data()
        
        print(f"Initialized new channel: {self.channel_username} with {self.num_videos} videos")
        logger.info(f"Initialized new channel: {self.channel_username} with {self.num_videos} videos")

        
    def update_dates(self) -> None:
        """
        Update the oldest and most recent dates from the dictionary of all videos.
        """
        if self.all_videos:
            dates = []
            for video_data in self.all_videos.values():
                published_at = video_data.get('published_at')
                if published_at:
                    # Convert the string date to a datetime object
                    date_obj = datetime.fromisoformat(published_at.rstrip('Z'))
                    dates.append(date_obj)
            
            # Find the oldest and most recent dates
            if dates:
                self.oldest_date = min(dates)
                self.most_recent_date = max(dates)

    def sync_channel_data(self) -> None:
        """
        Synchronize channel data with the database.
        """
        if self.db_connected:
            channel_data = {
                'channel_id': self.channel_id,
                'channel_username': self.channel_username,
                'channel_description': self.channel_description,
                'subscriber_count': self.subscriber_count,
                'view_count': self.view_count,
                'num_videos': self.num_videos,
                'thumbnails': self.channel_thumbnails,
                'oldest_date': self.oldest_date,
                'most_recent_date': self.most_recent_date
            }
            self.mongo.upsert_channel(channel_data)
            logger.info(f"Synchronized channel data for {self.channel_username}")
            

    def get_info(self) -> None:
        """
        Print information regarding the current channel
        """
        print('\n' + '='*50)
        print(f'INFO ABOUT THE CHANNEL:')
        print(f'Channel Username: {self.channel_username}')
        print(f'Channel ID: {self.channel_id}')
        print(f'Channel Description: {self.channel_description[:200]}...')
        print(f'Channel Keywords: {self.channel_keywords}')
        print(f'Subscriber Count: {self.subscriber_count}')
        print(f'Total Views: {self.view_count}')
        print(f'Total Videos Published: {self.num_videos}')
        if self.all_videos:
            print(f'Videos Retrieved: {len(self.all_videos)}')
            if self.oldest_date:
                print(f'Oldest Video Date: {self.oldest_date}')
            if self.most_recent_date:
                print(f'Most Recent Video Date: {self.most_recent_date}')
        print('='*50 + '\n')


    def verify_mongo_connection(self) -> bool:
        """
        Verify the MongoDB connection status.
        :return: True if connection is active, False otherwise
        """
        if self.mongo is None:
            return False
        
        try:
            # Attempt a simple operation to verify the connection
            self.mongo.client.admin.command('ismaster')
            return True
        except Exception as e:
            logger.error(f"MongoDB connection verification failed: {str(e)}")
            return False


    ### MAIN API CALLS


    def get_channel_upload_playlist_id(self) -> Union[str, None]:
        """
        Get the ID of the channel's 'Uploads' playlist.
        :return: Upload playlist ID or None if not found
        """
        try:
            request = self.youtube.channels().list(
                part="contentDetails",
                id=self.channel_id
            )
            response = request.execute()
            logger.info(f"API call: youtube.channels().list for channel ID: {self.channel_id}")
            
            return response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        except Exception as e:
            logger.error(f"Error getting upload playlist ID: {str(e)}", exc_info=True)
            return None


    def get_all_video_ids(self) -> List[str]:
        """
        Retrieve all video IDs from the channel's 'Uploads' playlist.
        :return: List of video IDs
        """
        upload_playlist_id = self.get_channel_upload_playlist_id()
        if not upload_playlist_id:
            return []
        
        video_ids = []
        next_page_token = None

        while True:
            try:
                # Fetch video IDs from the 'Uploads' playlist
                request = self.youtube.playlistItems().list(
                    part="contentDetails",
                    playlistId=upload_playlist_id,
                    maxResults=50,
                    pageToken=next_page_token
                )
                response = request.execute()
                logger.info(f"API call: youtube.playlistItems().list for playlist ID: {upload_playlist_id}")

                video_ids.extend([item['contentDetails']['videoId'] for item in response['items']])

                next_page_token = response.get('nextPageToken')
                if not next_page_token:
                    break

            except Exception as e:
                logger.error(f"Error retrieving video IDs: {str(e)}", exc_info=True)
                break

        logger.info(f"Retrieved {len(video_ids)} video IDs for channel: {self.channel_username}")
        return video_ids
    


    def create_empty_video_dict(self, video_id) -> Dict[str, Dict[str, Any]]:
        """
        Create an empty dictionary for all videos with None values.
        This is useful for initializing video data before populating it.
        :return: dictionary of video data
        """
        self.all_videos[video_id] = {
            'video_id': video_id,
            'title': None,
            'published_at': None,
            'description': None,
            'duration': None,
            'tags': None,
            'timestamps': None
        }


    def populate_video_data(self, batch_size: int = 50) -> None:
        """
        Populate video data in batches, updating self.all_videos after each batch.
        :param batch_size: number of video IDs to process in each batch
        """
        if not self.all_video_ids:
            self.all_video_ids = self.get_all_video_ids()

        if not self.all_video_ids:
            logger.error("Failed to retrieve video IDs")
            raise ValueError("No video IDs available to populate data")

        if self.all_videos is None:
            self.all_videos = {}

        for i in range(0, len(self.all_video_ids), batch_size):
            batch = self.all_video_ids[i:i+batch_size]
            # Initialize empty dictionary for each video ID
            for video_id in batch:
                self.create_empty_video_dict(video_id)

            self.process_video_batch(batch)

        self.update_dates()
        self.sync_channel_data()

    
    def process_video_batch(self, video_ids: List[str]) -> None:
        """
        Process a batch of video IDs to retrieve their data.
        :param video_ids: list of video IDs
        """
        # Fetch video details using the video IDs
        try:
            video_details = self.youtube.videos().list(
                part="snippet,contentDetails",
                id=','.join(video_ids)
            ).execute()

            for item in video_details.get('items', []):
                video_id = item['id']
                snippet = item['snippet']
                content_details = item['contentDetails']

                video_data = {
                    'title': snippet['title'],
                    'published_at': snippet['publishedAt'],
                    'description': snippet['description'],
                    'duration': content_details.get('duration', None),
                    'tags': snippet.get('tags', None),
                    'timestamps': extract_timestamps(snippet['description'])
                }

                self.all_videos[video_id] = video_data

            logger.info(f"Processed batch of {len(video_ids)} videos.")

        except HttpError as e:
            if e.resp.status == 403 and "quotaExceeded" in str(e):
                logger.error("YouTube API quota exceeded")
                raise QuotaExceededException("YouTube API quota exceeded")
            else:
                logger.error(f"HTTP error processing video batch: {str(e)}", exc_info=True)
                raise
        except Exception as e:
            logger.error(f"Error processing video batch: {str(e)}", exc_info=True)
            print(f"Error processing video batch: {str(e)}")
            raise

    
    def sync_videos(self) -> None:
        """
        Synchronize stored videos with the current state of the YouTube channel.
        This method handles cases where we already have some videos stored.
        """
        logger.info(f"Starting video synchronization for channel: {self.channel_username}")
        
        # Get all current video IDs from the channel
        current_video_ids = set(self.get_all_video_ids())
        stored_video_ids = set(self.all_videos.keys())
        
        # Find new videos (in current but not in stored)
        new_video_ids = current_video_ids - stored_video_ids
        print(f'Number of new videos detected: {len(new_video_ids)}')
        
        # Find removed videos (in stored but not in current)
        removed_video_ids = stored_video_ids - current_video_ids
        print(f'Number of videos no longer available: {len(removed_video_ids)}')
        
        # Remove videos that are no longer in the channel
        for video_id in removed_video_ids:
            del self.all_videos[video_id]
        
        # Fetch information for new videos
        if new_video_ids:
            try:
                self.fetch_new_videos(list(new_video_ids))
            except QuotaExceededException:
                logger.warning("Quota exceeded during sync. Sync is incomplete.")
                print("WARNING: YouTube API quota exceeded. Synchronization is incomplete.")
            except Exception as e:
                logger.error(f"Error during video synchronization: {str(e)}", exc_info=True)
        
        print(f"Video synchronization completed.")
        print(f"  - Added: {len(new_video_ids)} new videos")
        print(f"  - Removed: {len(removed_video_ids)} videos")
        print(f"  - Total videos after sync: {len(current_video_ids)}")
        logger.info(f"Video synchronization completed. Added: {len(new_video_ids)}, "
                    f"Removed: {len(removed_video_ids)}, Total: {self.num_videos}")

        self.num_videos = len(current_video_ids)
        # Update dates after synchronization
        self.update_dates()
        self.sync_channel_data()

    
    def fetch_new_videos(self, video_ids: List[str], batch_size: int = 50) -> None:
        """
        Fetch information for new videos in batches.
        :param video_ids: list of new video IDs
        :param batch_size: number of video IDs to process in each batch
        """
        for i in range(0, len(video_ids), batch_size):
            batch = video_ids[i:i+batch_size]
            try:
                self.process_video_batch(batch)
                logger.info(f"Processed batch of {len(batch)} new videos")
            except QuotaExceededException:
                logger.warning(f"Quota exceeded. Processed {i} videos out of {len(video_ids)}")
                break
            except Exception as e:
                logger.error(f"Error processing video batch: {str(e)}", exc_info=True)
                break


    def get_videos_dataframe(self) -> pd.DataFrame:
        """
        convert the all_videos dictionary to a pandas DataFrame.
        :return: DataFrame of video information
        """
        if not self.all_videos:
            return pd.DataFrame()

        videos_list = []
        for video_id, video_data in self.all_videos.items():
            video_info = {
                'video_id': video_id,
                'title': video_data['title'],
                'published_at': video_data['published_at'],
                'duration': video_data.get('duration', 'N/A'),
                'description': video_data['description'][:400] + '...' if len(video_data['description']) > 400 else video_data['description'],
                'tags': video_data.get('tags', None),
                'timestamps': video_data['timestamps'],              #video_data.get('timestamps', None)
            }
            videos_list.append(video_info)

        df = pd.DataFrame(videos_list)
        df['published_at'] = pd.to_datetime(df['published_at'])
        df = df.sort_values('published_at', ascending=False).reset_index(drop=True)

        return df
    

    def save_data(self):

        # Sort the videos
        self.all_videos = sort_videos_by_date(self.all_videos)

        # Update the videos to the database
        if self.db_connected:
            self.mongo.sync_videos(self.channel_username, self.all_videos)
        
        # Save the videos to a local JSON file
        filename = f"{self.channel_username.replace(' ', '')}_videos.json"
        folder_path = 'Channel_Videos'
        file_path = os.path.join(folder_path, filename)
        
        #os.makedirs(folder_path, exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(self.all_videos, f, indent=4)     # indent allows to get tab spacing
        print(f"Video data has been saved to {file_path}")
        logger.info(f"Saved {len(self.all_videos)} videos to {file_path}")
            

    def close_connection(self):
        """
        Close the MongoDB connection if it's open.
        """
        if self.db_connected and self.mongo:
            self.mongo.close()
            self.db_connected = False
            print("MongoDB connection closed.")
            logger.info("MongoDB connection closed.")

            
