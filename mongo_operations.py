import os
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from dotenv import load_dotenv
from logging_config import logger


class MongoOperations:
    """
    A class to handle MongoDB operations for the YouTube Channel Analyzer.
    """

    def __init__(self):
        """
        Initialize the MongoOperations class.
        Loads environment variables and sets up initial connection attributes.
        """
        load_dotenv()
        self.client = None
        self.db = None

    def connect(self) -> bool:
        """
        Establish a connection to the MongoDB database.
        :return: True if connection is successful, False otherwise
        """
        try:
            # Attempt to connect to MongoDB using environment variables
            self.client = MongoClient(
                host=os.getenv('MONGO_HOST', 'localhost'),
                port=int(os.getenv('MONGO_PORT', 27017)),
                username=os.getenv('MONGO_USERNAME', 'admin'),
                password=os.getenv('MONGO_PASSWORD', 'password'),
                serverSelectionTimeoutMS=5000   # 5 second timeout
            )
            # Force a connection attempt to verify
            self.client.admin.command('ismaster')
            self.db = self.client[os.getenv('MONGO_DB', 'youtube_tracker')]
            print("Connected to MongoDB successfully!")
            logger.info("Connected to MongoDB successfully!")
            return True
        except ConnectionFailure as e:
            print(f"Failed to connect to MongoDB: {e}")
            logger.error(f"Failed to connect to MongoDB: {e}")
            return False
        except Exception as e:
            print(f"An error occurred while connecting to MongoDB: {e}")
            logger.error(f"An error occurred while connecting to MongoDB: {e}")
            return False
        
    def verify_connection(self) -> bool:
        """
        Verify the MongoDB connection status.
        :return: True if connection is active, False otherwise
        """
        if self.client is None:
            return False
        
        try:
            # Attempt a simple operation to verify the connection
            self.client.admin.command('ismaster')
            return True
        except Exception as e:
            logger.error(f"MongoDB connection verification failed: {str(e)}")
            return False

    def close(self):
        """
        Close the MongoDB connection if it exists.
        """
        if self.client:
            self.client.close()
            print("MongoDB connection closed.")
            logger.info("MongoDB connection closed.")

    # CHANNEL OPERATIONS

    def upsert_channel(self, channel_data):
        """
        Insert or update a channel document in the database.
        :param channel_data: Dictionary containing channel information
        :return: The channel_username of the upserted document
        """
        try:
            # Update or insert the channel document
            result = self.db.channels.update_one(
                {"channel_username": channel_data['channel_username']},     # unique identifier
                {"$set": channel_data},
                upsert=True
            )
            if result.upserted_id:
                logger.info(f"Channel inserted: {channel_data['channel_username']}")
            else:
                logger.info(f"Channel updated: {channel_data['channel_username']}")
            
            # Check if the collection exists before creating it
            if channel_data['channel_username'] not in self.db.list_collection_names():
                self.db.create_collection(channel_data['channel_username'])
            
            return channel_data['channel_username']
        except Exception as e:
            logger.error(f"Error upserting channel {channel_data['channel_username']}: {e}")

    def get_channel(self, channel_username):
        """
        Retrieve a channel document from the database.
        :param channel_username: The username of the channel to retrieve
        :return: The channel document if found, None otherwise
        """
        try:
            channel = self.db.channels.find_one({"channel_username": channel_username})
            if channel:
                logger.info(f"Retrieved channel: {channel_username}")
            else:
                logger.info(f"Channel not found: {channel_username}")
            return channel
        except Exception as e:
            logger.error(f"Error retrieving channel {channel_username}: {e}")

    def get_all_channels(self):
        """
        Retrieve all channel documents from the database.
        :return: A list of all channel documents
        """
        try:
            channels = list(self.db.channels.find())
            logger.info(f"Retrieved {len(channels)} channels")
            return channels
        except Exception as e:
            logger.error(f"Error retrieving all channels: {e}")


    # VIDEO OPERATIONS
    
    def upsert_video(self, channel_username, video_id, video_data):
        """
        Insert or update a video document in the database.
        :param channel_username: The username of the channel the video belongs to
        :param video_id: The ID of the video
        :param video_data: Dictionary containing video information
        """
        try:
            collection = self.db[channel_username]
            result = collection.update_one(
                {"_id": video_id},
                {"$set": video_data},
                upsert=True
            )
            if result.upserted_id:
                logger.info(f"New video inserted: {video_id} for channel {channel_username}")
            else:
                logger.info(f"Existing video updated: {video_id} for channel {channel_username}")
        except Exception as e:
            logger.error(f"Error upserting video {video_id} for {channel_username}: {e}")


    def get_video(self, channel_username, video_id):
        """
        Retrieve a video document from the database.
        :param channel_username: The username of the channel the video belongs to
        :param video_id: The ID of the video to retrieve
        :return: The video document if found, None otherwise
        """
        try:
            collection = self.db[channel_username]
            video = collection.find_one({"_id": video_id})
            if video:
                logger.info(f"Retrieved video: {video_id} from channel {channel_username}")
            else:
                logger.info(f"Video not found: {video_id} in channel {channel_username}")
            return video
        except Exception as e:
            logger.error(f"Error retrieving video: {e}")


    def get_all_videos(self, channel_username):
        """
        Retrieve all video documents for a specific channel.
        :param channel_username: The username of the channel to retrieve videos from
        :return: A list of all video documents for the channel
        """
        try:
            collection = self.db[channel_username]
            videos = list(collection.find())
            print(f"Retrieved {len(videos)} videos for channel {channel_username}")
            return videos
        except Exception as e:
            logger.error(f"Error retrieving all videos: {e}")


    def sync_videos(self, channel_username, all_videos):
        """
        Synchronize the videos in the database with the provided video data.
        :param channel_username: The username of the channel to sync videos for
        :param all_videos: Dictionary containing all current video data
        """

        logger.info(f"Starting MongoDB sync for channel {channel_username}")
        try:
            collection = self.db[channel_username]
            
            # Get existing video IDs
            existing_videos = set(doc["_id"] for doc in collection.find({}, {"_id": 1}))
            logger.info(f"Found {len(existing_videos)} existing videos in MongoDB")

            # Upsert videos
            for video_id, video_data in all_videos.items():
                self.upsert_video(channel_username, video_id, video_data)
                if video_id in existing_videos:
                    existing_videos.remove(video_id)

            # Remove videos that no longer exist
            for video_id in existing_videos:
                self.delete_video(channel_username, video_id)

            # Update the video count in the channels collection
            self.db.channels.update_one(
                {"channel_username": channel_username},
                {"$set": {"num_videos": len(all_videos)}}
            )

            logger.info(f"MongoDB sync completed for channel {channel_username}")
            logger.info(f"Synced {len(all_videos)} videos, removed {len(existing_videos)} obsolete videos")
            print(f"Synced {len(all_videos)} videos for channel {channel_username}")
            print(f"Removed {len(existing_videos)} obsolete videos")
        except Exception as e:
            logger.error(f"Error syncing videos: {e}")


    def delete_video(self, channel_username, video_id):
        """
        Delete a video document from the database.
        :param channel_username: The username of the channel the video belongs to
        :param video_id: The ID of the video to delete
        :return: The number of documents deleted (0 or 1)
        """
        try:
            collection = self.db[channel_username]
            result = collection.delete_one({"_id": video_id})
            if result.deleted_count > 0:
                logger.info(f"Video deleted: {video_id} from channel {channel_username}")
            else:
                logger.info(f"No video found to delete: {video_id} in channel {channel_username}")
            return result.deleted_count
        except Exception as e:
            logger.error(f"Error deleting video: {e}")