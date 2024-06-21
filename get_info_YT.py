import re
import os
import json
import pytz
from datetime import datetime
from dotenv import load_dotenv
from googleapiclient.discovery import build


load_dotenv()


def check_file_exists(filename):
    """
    check if a file exists in the current directory.
    """
    return os.path.exists(filename)

    
def to_rfc3339_format(date):
    """
    Convert a datetime object to an RFC 3339 formatted date-time string.
    """
    if date.tzinfo is None:
        date = date.replace(tzinfo=pytz.UTC)
    return date.isoformat()


def extract_video_id(url):
    """
    extracts the video ID from a YouTube URL.
    """
    video_id_match = re.search(r'(?:v=|youtu\.be/|/v/|/embed/|/shorts/)([^\s&?]+)', url)
    if video_id_match:
        return video_id_match.group(1)
    return None


def extract_channel_id(url):
    """
    extracts the channel ID or username from a YouTube URL.
    """
    channel_id_match = re.search(r'(?:youtube\.com/(?:c/|channel/|user/|@))([^/?&]+)', url)
    if channel_id_match:
        return channel_id_match.group(1)
    return None


def get_channel_id_from_url(youtube, url):
    """
    retrieves the channel ID from a YouTube URL.
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
            """
            # fetch channel details using the username/custom URL
            request = youtube.channels().list(
                part="id",
                forUsername=channel_id_username
            )
            response = request.execute()

            if 'items' in response and len(response['items']) > 0:
                channel_details = response['items'][0]
                print(channel_details)
                channel_id = channel_details['id']
                channel_title = channel_details['snippet']['title']
                return channel_id, channel_title
            else:
            """
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
    

def extract_timestamps(description):
    """
    extracts timestamps and their corresponding subtitles from the video description if present.
    """
    timestamp_pattern = re.compile(r'(\d{1,2}:\d{2}(?::\d{2})?)\s*([^\n]*)')    # matches MM:SS or HH:MM:SS followed by subtitles
    matches = timestamp_pattern.findall(description)
    timestamps = {match[0]: match[1].strip() for match in matches}
    return timestamps if timestamps else None

    

DEVELOPER_KEY = os.getenv('YOUTUBE_API_KEY')
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=DEVELOPER_KEY)

today_dt = datetime.now()
today_str = to_rfc3339_format(today_dt)


class InfoYT():

    def __init__(self, url) -> None:

        channel_id, channel_username = get_channel_id_from_url(youtube, url)
        self.channel_id = channel_id
        self.channel_username = channel_username
        self.num_videos = self.get_video_count(youtube)
        self.all_videos = None


    def get_info(self):
        """
        print information regarding the current channel
        """

        print(f'The username for this channel is: {self.channel_username}.')
        print(f'The channel id is: {self.channel_id}')
        print(f'The number of video published by this channel is: {self.num_videos}.')


    def check_history(self):

        filename = self.channel_username.replace(' ','_')+'_videos.json'
        folder_path = 'Channel_Videos'
        file_path = os.path.join(folder_path, filename) 

        if os.path.exists(folder_path):
            if os.path.isfile(file_path):
                print(f"The file {filename} already exists.")
                return True
            else:
                print(f"The file {filename} doesn't exist yet in the {folder_path}/ folder. \
                      There is no history record for this channel.")
                return False
        else:
            # create the folder if it doesn't exist
            os.makedirs(folder_path)
            print(f"The folder '{folder_path}' has been created. No files were previously stored.")
            return False
        
    
    def get_video_count(self, youtube=youtube):
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
    

    def get_recent_videos(self, max_result = 15, date=today_str, youtube=youtube):
        """
        retrieve recently uploaded video information from one YouTube channel.
        """
        videos = []

        request = youtube.search().list(
            part="snippet",
            channelId=self.channel_id,
            publishedBefore = date,
            maxResults=max_result,      # max requests are 50
            order="date",
        )
        response = request.execute()
        
        for item in response['items']:
            if item['id']['kind'] == 'youtube#video':
                video_id = item['id']['videoId']
                video_info = youtube.videos().list(
                    part="snippet,contentDetails",
                    id=video_id
                ).execute()
                for video in video_info['items']:
                    description = video['snippet']['description']
                    video_data = {
                        'video_id': video['id'],
                        'title': video['snippet']['title'],
                        'published_at': video['snippet']['publishedAt'],
                        'duration': video['contentDetails']['duration'],
                        'description': description,
                        'timestamps': extract_timestamps(description)
                    }
                    videos.append(video_data)

        return videos
    
    def get_all_videos(self, max_videos=200, youtube=youtube):
        """
        retrieve video information for ALL the videos of one YouTube channel.
        """
        videos = []
        next_page_token = None

        if self.num_videos>max_videos:
            reply = input(f'The number of videos in this channel is {self.num_videos}. \
                            This download will retrieve only {max_videos} videos. You can overwrite this \
                            by setting the parameter max_videos to whatever you desire, but be mindful of \
                            the YouTube API limit. Want to proceed? Y/N')
            if reply.lower()=='n':
                return None
        
        counter = 0
        while True:
            request = youtube.search().list(
                part="snippet",
                channelId=self.channel_id,
                maxResults=26,      # 50 is the maximum allowed by API
                order="date",
                pageToken = next_page_token,
            )
            response = request.execute()
            
            for item in response['items']:
                if item['id']['kind'] == 'youtube#video':
                    video_id = item['id']['videoId']
                    video_info = youtube.videos().list(
                        part="snippet,contentDetails",
                        id=video_id
                    ).execute()
                    for video in video_info['items']:
                        description = video['snippet']['description']
                        video_data = {
                            'video_id': video['id'],
                            'title': video['snippet']['title'],
                            'published_at': video['snippet']['publishedAt'],
                            'duration': video['contentDetails']['duration'],
                            'description': description,
                            'timestamps': extract_timestamps(description)
                        }
                        videos.append(video_data)
                        counter+=1
                        if counter>max_videos:
                            break
            
            if counter>max_videos:
                break
            next_page_token = response.get('nextPageToken')
            if not next_page_token:
                break

        if len(videos)>=0.95*self.num_videos:
            print('All the videos in the channel have been retrieved!')

        videos_dict = {item['video_id']: item for item in videos}

        self.all_videos = videos_dict
        #return videos


    def get_dates(self):
        """
        retrieve the oldest and most recent dates from the dictionary of all videos.
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
    

    def save_to_json(self):
        """
        saves a dictionary to a JSON file in a specific folder.
        """
        filename = self.channel_username.replace(' ','_')+'_videos.json'
        folder_path = 'Channel_Videos'
        file_path = os.path.join(folder_path, filename)

        with open(file_path, 'w') as f:
            json.dump(self.all_videos, f, indent=4)    # indent allows to get tab spacing
            print(f"Video data has been saved to {file_path}")


    def load_from_json(self):
        """
        loads a dictionary from a JSON file in a specific folder.
        """
        filename = self.channel_username.replace(' ','_')+'_videos.json'
        folder_path = 'Channel_Videos'
        file_path = os.path.join(folder_path, filename) 
        with open(file_path, 'r') as f:
            self.all_videos = json.load(f)
            #return json.load(f)


    def update_videos(self):

        counter = 0
        titles = []

        new_videos = self.get_recent_videos(max_result=25)
            
        for video in new_videos:
            video_id = video['video_id']
            if video_id not in self.all_videos:
                self.all_videos[video_id] = video
                counter += 1
                titles.append(video['title'])
            

        print(f"I've found {counter} new videos to be added!")
        if counter>0:
            print(f'Here are the titles of the new videos:')
            for title in titles:
                print(f'{title}')

