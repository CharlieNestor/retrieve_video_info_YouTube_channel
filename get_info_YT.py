import re
import os
import json
import pytz
from typing import List, Dict, Any, Tuple, Union
from datetime import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build

# load the environment variables
load_dotenv()

    
def to_rfc3339_format(date: datetime) -> str:
    """
    convert a datetime object to an RFC 3339 formatted date-time string.
    """
    if date.tzinfo is None:
        date = date.replace(tzinfo=pytz.UTC)
    return date.isoformat()


def extract_video_id(url:str) -> Union[str, None]:
    """
    extract the video ID from a YouTube URL.
    """
    video_id_match = re.search(r'(?:v=|youtu\.be/|/v/|/embed/|/shorts/)([^\s&?]+)', url)
    if video_id_match:
        return video_id_match.group(1)
    return None


def extract_channel_id(url:str) -> Union[str, None]:
    """
    extract the channel ID or username from a YouTube URL.
    """
    channel_id_match = re.search(r'(?:youtube\.com/(?:c/|channel/|user/|@))([^/?&]+)', url)
    if channel_id_match:
        return channel_id_match.group(1)
    return None


def get_channel_id_from_url(youtube, url:str) -> tuple:
    """
    retrieve the channel ID and channel username from a YouTube URL.
    """

    # try to extract video ID
    video_id = extract_video_id(url)
    if video_id:
        # fetch video details using the video ID
        request = youtube.videos().list(
            part="snippet",
            id=video_id
        )
        response = request.execute()

        if 'items' in response and len(response['items']) > 0:
            video_details = response['items'][0]
            channel_id = video_details['snippet']['channelId']
            channel_title = video_details['snippet']['channelTitle']
            return channel_id, channel_title
        else:
            raise ValueError("Video not found")

    # try to extract channel ID or username
    channel_id_username = extract_channel_id(url)
    if channel_id_username:
        # check if it's a channel ID (starts with 'UC') or username/custom URL
        if channel_id_username.startswith('UC'):
            return channel_id_username, None
        else:
            # try to fetch channel details using custom URL handling
            request = youtube.search().list(
                part="snippet",
                q=channel_id_username,      # this is literally making a query for parameter q
                type="channel",
                maxResults=1
            )
            response = request.execute()
            
            if 'items' in response and len(response['items']) > 0:
                channel_details = response['items'][0]
                channel_id = channel_details['snippet']['channelId']
                channel_title = channel_details['snippet']['channelTitle']
                return channel_id, channel_title
            else:
                raise ValueError("Channel not found")
    else:
        raise ValueError("Invalid YouTube URL")
    

def extract_timestamps(description:str) -> dict:
    """
    extract timestamps and their corresponding subtitles from the video description, if present.
    """
    timestamp_pattern = re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?)\s*([^\n]*)')    # matches MM:SS or HH:MM:SS followed by subtitles
    matches = timestamp_pattern.findall(description)
    timestamps = {match[0]: match[1].strip() for match in matches}
    return timestamps if timestamps else None


def sort_videos_by_date(videos_dict: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """
    sort the videos dictionary by 'published_at' field in decreasing order (most recent first).
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

    

DEVELOPER_KEY = os.getenv('YOUTUBE_API_KEY')
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=DEVELOPER_KEY)

today_dt = datetime.now()
today_str = to_rfc3339_format(today_dt)


class InfoYT():
    """
    this class retrieves information about a YouTube channel and its videos.
    input: a YouTube channel URL
    output: information about the channel and its videos
    """

    def __init__(self, url:str) -> None:

        channel_id, channel_username = get_channel_id_from_url(youtube, url)
        self.channel_id = channel_id
        self.channel_username = channel_username
        self.num_videos = self.get_video_count(youtube)
        self.all_videos = self.load_from_json() if self.check_history() else None
        if self.all_videos:
            self.get_dates()
        self.get_info()


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
            self.get_dates()
            if self.oldest_date:
                print(f'The oldest video was published on: {self.oldest_date}')
            if self.most_recent_date:
                print(f'The most recent video was published on: {self.most_recent_date}')


    def check_history(self) -> bool:
        """
        check if a file with the channel's videos already exists in the Channel_Videos folder.
        """
        filename = self.channel_username.replace(' ','')+'_videos.json'
        folder_path = 'Channel_Videos'
        file_path = os.path.join(folder_path, filename) 

        if os.path.exists(folder_path):
            if os.path.isfile(file_path):
                print(f"We already have history record for this channel in the file {filename}.")
                return True
            else:
                print(f"The file {filename} doesn't exist yet in the {folder_path}/ folder. \nThere is no history record for this channel.")
                return False
        else:
            # create the folder if it doesn't exist
            os.makedirs(folder_path)
            print(f"The folder '{folder_path}' has been created. No files were previously stored.")
            return False
        
    
    def get_video_count(self, youtube=youtube) -> int:
        """
        retrieve the total number of videos of a YouTube channel.
        """
        # fetch channel details
        request = youtube.channels().list(
            part="statistics",
            id=self.channel_id
        )
        response = request.execute()

        if 'items' in response and len(response['items']) > 0:
            channel_stats = response['items'][0]['statistics']
            video_count = channel_stats.get('videoCount')
            return int(video_count)
        else:
            raise ValueError("Channel not found")
        

    def get_dates(self) -> None:
        """
        update the oldest and most recent dates from the dictionary of all videos.
        """
        dates = []
        if self.all_videos:
            for video_id, video_data in self.all_videos.items():
                published_at = video_data.get('published_at')
                if published_at:
                    # convert the string date to a datetime object
                    date_obj = datetime.fromisoformat(published_at.rstrip('Z'))
                    dates.append(date_obj)
            
            # find the oldest and most recent dates
            if dates:
                oldest_date = min(dates)
                most_recent_date = max(dates)
                self.oldest_date = oldest_date
                self.most_recent_date = most_recent_date
                #return oldest_date, most_recent_date
            else:
                self.oldest_date = None
                self.most_recent_date = None
                #return None, None
        else:
            self.oldest_date = None
            self.most_recent_date = None
    

    def get_recent_videos(self, max_result:int = 15, date=today_str, youtube=youtube) -> list:
        """
        retrieve recently uploaded video information from one YouTube channel.
        """
        videos = []

        request = youtube.search().list(
            part="snippet",
            channelId=self.channel_id,
            publishedBefore = date,
            maxResults=max_result,      # max requests are 50
            order="date",               # order by date (other values are relevance, rating, viewCount, title)
            type='video'                # only retrieve videos
        )
        response = request.execute()

        for item in response['items']:
            #print(item)
            video_data = {
                'video_id': item['id']['videoId'],
                'title': item['snippet']['title'],
                'published_at': item['snippet']['publishedAt'],
                'description': item['snippet']['description'],
                'timestamps': extract_timestamps(item['snippet']['description'])
            }
            videos.append(video_data)

        # batch request allows to retrieve the duration of multiple videos with few/one request
        batch = [video['video_id'] for video in videos]
        video_details = youtube.videos().list(
            part="contentDetails",
            id=','.join(batch)
        ).execute()
        for detail in video_details['items']:
            #print(detail)
            video_id = detail['id']
            duration = detail['contentDetails']['duration']
            # Find the corresponding video in our list and update it
            for video in videos:
                if video['video_id'] == video_id:
                    video['duration'] = duration
                    break

        return videos
    
    def get_all_videos(self, max_videos:int=200, youtube=youtube) -> None:
        """
        retrieve video information for ALL the videos of one YouTube channel.
        due to API limits this will retrieve only a default maximum of 200 videos.
        """
        videos = []
        next_page_token = None
        published_before = today_str

        # check if there is a history record for this channel
        if not self.all_videos:
            if self.num_videos>max_videos:
                # warn the user of API limits and ask for confirmation
                reply = input(f'The number of videos in this channel is {self.num_videos}.\nThis download will \
                                retrieve only {max_videos} videos. You can overwrite this \
                                by setting the parameter max_videos to whatever you desire, but be mindful of \
                                the YouTube API limit. Want to proceed? Y/N')
                if reply.lower()=='n':
                    return None
        # check if the number of videos already retrieved is close to the total number of videos
        elif len(self.all_videos)<0.9*self.num_videos:
            # update oldest date
            self.get_dates()
            print(f'The number of videos already retrieved is {len(self.all_videos)}. \nThis download will \
                retrieve videos published before {self.oldest_date}.')
            published_before = to_rfc3339_format(self.oldest_date)
        else:
            # the current record stores already > 90% of the videos
            print('All the videos in the channel have already been retrieved!')
            return None
        
        # requests for videos until the maximum number of videos is reached
        while True:
            request = youtube.search().list(
                part="snippet",
                channelId=self.channel_id,
                maxResults=26,      # 50 is the maximum allowed by API
                order="date",
                type='video',
                publishedBefore=published_before,
                pageToken = next_page_token,
            )
            response = request.execute()

            for item in response['items']:
                video_data = {
                    'video_id': item['id']['videoId'],
                    'title': item['snippet']['title'],
                    'published_at': item['snippet']['publishedAt'],
                    'description': item['snippet']['description'],
                    'timestamps': extract_timestamps(item['snippet']['description'])
                }
                videos.append(video_data)
            
            # if there is no next page token, break the while loop
            next_page_token = response.get('nextPageToken')
            if not next_page_token or len(videos) >= max_videos:
                break
            # once the maximum number of videos is reached, break the while loop
            if len(videos) >= max_videos:
                break

        # batch requests to retrieve the duration of multiple videos with few requests
        video_ids = [video['video_id'] for video in videos]
        for i in range(0, len(video_ids), 50):  # Process in batches of 50
            batch = video_ids[i:i+50]
            video_details = youtube.videos().list(
                part="contentDetails",
                id=','.join(batch)
            ).execute()

            for detail in video_details['items']:
                video_id = detail['id']
                duration = detail['contentDetails']['duration']
                # Find the corresponding video in our list and update it
                for video in videos:
                    if video['video_id'] == video_id:
                        video['duration'] = duration
                        break

        if self.all_videos:
            for video in videos:
                video_id = video['video_id']
                if video_id not in self.all_videos:
                    self.all_videos[video_id] = video
            if (len(videos) + len(self.all_videos)) >= 0.95*self.num_videos:
                print('All the videos in the channel have been retrieved!')
        else:
            videos_dict = {item['video_id']: item for item in videos}
            self.all_videos = videos_dict
            if len(videos) >= 0.95*self.num_videos:
                print('All the videos in the channel have been retrieved!')

        # the dictionary of all videos has been updated, now update the oldest and most recent dates
        self.get_dates()
        print(f'This download has retrieved {len(videos)} videos.')
    

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


    def load_from_json(self) -> dict:
        """
        loads a dictionary from a JSON file in a specific folder.
        """
        filename = self.channel_username.replace(' ','')+'_videos.json'
        folder_path = 'Channel_Videos'
        file_path = os.path.join(folder_path, filename) 
        with open(file_path, 'r') as f:
            #self.all_videos = json.load(f)
            return json.load(f)


    def update_videos(self, max_result:int=25) -> None:
        """
        retrieves the most recent videos and adds them to the dictionary of all videos.
        """
        counter = 0
        titles = []

        if self.all_videos:
            
            new_videos = self.get_recent_videos(max_result=max_result)
            
            for video in new_videos:
                video_id = video['video_id']
                if video_id not in self.all_videos:
                    self.all_videos[video_id] = video
                    counter += 1
                    titles.append(video['title'])
            # the dictionary of all videos has been updated, now update the oldest and most recent dates
            self.get_dates()
            
            print(f"I've found {counter} new videos to be added!")
            if counter>0:
                print(f'Here are the titles of the new videos:')
                for title in titles:
                    print(f'{title}')
            
            if counter==max_result:
                print('There are more than 25 new videos. \
                      You can run the update_videos method again with max_result up to 50 to retrieve more.')
        else:
            print('No videos have been retrieved yet. Please run the get_all_videos method first.')

