import re
import os
import json
import pytz
import random
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from typing import List, Dict, Any, Tuple, Union


# Load the environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    filename='youtube_data_tool.log')
logger = logging.getLogger(__name__)

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


def get_channel_id_from_url(youtube, url:str) -> Tuple[str, Union[str, None]]:
    """
    retrieve the channel ID and channel username from a YouTube URL.
    :param youtube: YouTube API client
    :param url: YouTube URL
    :return: channel ID and channel
    """
    try:
        # Try to extract video ID
        video_id = extract_video_id(url)
        if video_id:
            # Specific single request using video ID
            request = youtube.videos().list(
                part="snippet",
                id=video_id
            )
            response = request.execute()
            logger.info(f"API call: youtube.videos().list for video ID: {video_id}")

            if 'items' in response and len(response['items']) > 0:
                video_details = response['items'][0]
                channel_id = video_details['snippet']['channelId']
                channel_title = video_details['snippet']['channelTitle']
                logger.info(f"Successfully retrieved channel info for video ID: {video_id}")
                return channel_id, channel_title
            else:
                logger.warning(f"No video found for ID: {video_id}")
                raise ValueError("Video not found")

        # Try to extract channel ID or username
        channel_id_username = extract_channel_id(url)
        if channel_id_username:
            # Check if it's a channel ID (starts with 'UC') or username/custom URL
            if channel_id_username.startswith('UC'):
                logger.info(f"Channel ID found: {channel_id_username}")
                return channel_id_username, None
            else:
                # Try to fetch channel details using a search query
                request = youtube.search().list(
                    part="snippet",
                    q=channel_id_username,      # this is literally making a query for parameter q
                    type="channel",             # only search for channels
                    maxResults=1
                )
                response = request.execute()
                logger.info(f"API call: youtube.search().list for channel: {channel_id_username}")
                
                if 'items' in response and len(response['items']) > 0:
                    channel_details = response['items'][0]
                    channel_id = channel_details['snippet']['channelId']
                    channel_title = channel_details['snippet']['channelTitle']
                    logger.info(f"Successfully retrieved channel info for username: {channel_id_username}")
                    return channel_id, channel_title
                
        logger.error(f"Invalid YouTube URL: {url}")
        raise ValueError("Invalid YouTube URL")
        
    except Exception as e:
        logger.error(f"Error in get_channel_id_from_url: {str(e)}", exc_info=True)
        raise ValueError("Error in get_channel_id_from_url")
    

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
    this class retrieves information about a YouTube channel and its videos.
    """

    def __init__(self, url: str) -> None:
        """
        Initialize the InfoYT object with a YouTube channel URL.
        :param url: YouTube channel URL
        """

        # Initialize YouTube API client
        self.youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=DEVELOPER_KEY)
        
        # Get channel ID and username from URL
        channel_id, channel_username = get_channel_id_from_url(self.youtube, url)
        self.channel_id = channel_id
        self.channel_username = channel_username
        self.num_videos = self.get_video_count()
        self.all_videos = self.load_from_json() if self.check_history(verbose=True) else None
        self.oldest_date = None
        self.most_recent_date = None
        # Check for existing data
        if self.check_history(verbose=False):
            self.update_dates()
        else:
            self.initialize_new_channel()
        # Print overall channel info
        self.get_info()


    ### INITIALIZATION METHODS

    def get_video_count(self) -> int:
        """
        retrieve the total number of videos of a YouTube channel.
        :return: number of videos
        """
        try:
            # Fetch channel details
            request = self.youtube.channels().list(
                part="statistics",
                id=self.channel_id
            )
            response = request.execute()
            logger.info(f"API call: youtube.channels().list for channel ID: {self.channel_id}")

            if 'items' in response and len(response['items']) > 0:
                channel_stats = response['items'][0]['statistics']
                video_count = channel_stats.get('videoCount')
                return int(video_count)
            else:
                raise ValueError("Channel not found")
        except Exception as e:
            logger.error(f"Error in get_video_count: {str(e)}", exc_info=True)
            raise ValueError("Error in get_video_count")
        

    def check_history(self, verbose=True) -> bool:
        """
        Check if a file with the channel's videos already exists in the Channel_Videos folder.
        If the folder doesn't exist, it will be created.
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
        

    def load_from_json(self) -> dict:
        """
        loads a dictionary from a JSON file in a specific folder.
        :return: dictionary of video data
        """
        filename = self.channel_username.replace(' ','')+'_videos.json'
        folder_path = 'Channel_Videos'
        file_path = os.path.join(folder_path, filename) 
        with open(file_path, 'r') as f:
            logger.info(f"Loaded video data from {file_path}")
            return json.load(f)
            
        
    
    def save_to_json(self) -> None:
        """
        saves a dictionary to a JSON file in a specific folder.
        """
        # Sort the videos
        sorted_videos = sort_videos_by_date(self.all_videos)

        filename = self.channel_username.replace(' ','')+'_videos.json'
        folder_path = 'Channel_Videos'
        file_path = os.path.join(folder_path, filename)

        with open(file_path, 'w') as f:
            json.dump(sorted_videos, f, indent=4)    # indent allows to get tab spacing
            print(f"Video data has been saved to {file_path}")
            logger.info(f"Saved video data to {file_path}")

        
    def update_dates(self) -> None:
        """
        Update the oldest and most recent dates from the dictionary of all videos.
        """
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
            logger.info(f"Updated date range for channel {self.channel_username}: "
                    f"oldest {self.oldest_date}, most recent {self.most_recent_date}")
            

    def initialize_new_channel(self) -> None:
        """
        Initialize data for a new channel with no existing record.
        If the channel has 200 or fewer videos, retrieve all video IDs.
        Otherwise, set a flag for lazy loading.
        """
        if self.num_videos <= 300:
            self.all_video_ids = self.get_all_video_ids()
        else:
            self.lazy_load = True
            self.all_video_ids = None       # Will be populated later as needed
        
        logger.info(f"Initialized new channel: {self.channel_username} with {self.num_videos} videos")

            

    def get_info(self) -> None:
        """
        print information regarding the current channel
        """
        print('')
        print(f'INFO ABOUT THE CHANNEL:')
        print(f'The username for this channel is: {self.channel_username}.')
        print(f'The channel id is: {self.channel_id}')
        print(f'The number of videos published by this channel is: {self.num_videos}.')
        if self.all_videos:
            print(f'The number of videos already retrieved is: {len(self.all_videos)}')
            if self.oldest_date:
                print(f'The oldest video was published on: {self.oldest_date}')
            if self.most_recent_date:
                print(f'The most recent video was published on: {self.most_recent_date}')


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

                self.all_videos[video_id] = {
                    'title': snippet['title'],
                    'published_at': snippet['publishedAt'],
                    'description': snippet['description'],
                    'duration': content_details['duration'],
                    'tags': snippet.get('tags'),
                    'timestamps': extract_timestamps(snippet['description'])
                }

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
        
        if self.all_videos is None:
            self.all_videos = {}
        
        stored_video_ids = set(self.all_videos.keys())
        
        # Find new videos (in current but not in stored)
        new_video_ids = current_video_ids - stored_video_ids
        print(f'The number of new videos is: {len(new_video_ids)}')
        
        # Find removed videos (in stored but not in current)
        removed_video_ids = stored_video_ids - current_video_ids
        print(f'The number of removed videos is: {len(removed_video_ids)}')
        
        # Remove videos that are no longer in the channel
        for video_id in removed_video_ids:
            del self.all_videos[video_id]
            logger.info(f"Removed video {video_id} from storage as it's no longer in the channel")
        
        # Fetch information for new videos
        if new_video_ids:
            try:
                self.fetch_new_videos(list(new_video_ids))
            except QuotaExceededException:
                logger.warning("Quota exceeded during sync. Sync is incomplete.")
        
        print(f"Video synchronization completed. Added {len(new_video_ids)} new videos, removed {len(removed_video_ids)} videos.")
        logger.info(f"Video synchronization completed. Added {len(new_video_ids)} new videos, removed {len(removed_video_ids)} videos.")
        
        # Update dates after synchronization
        self.update_dates()

    
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
                logger.error(f"Error processing batch: {str(e)}")
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
                'description': video_data['description'][:300] + '...' if len(video_data['description']) > 300 else video_data['description'],
                'tags': video_data.get('tags', None),
                'timestamps': video_data['timestamps'],              #video_data.get('timestamps', None)
            }
            videos_list.append(video_info)

        df = pd.DataFrame(videos_list)
        df['published_at'] = pd.to_datetime(df['published_at'])
        df = df.sort_values('published_at', ascending=False).reset_index(drop=True)
        return df
            
