import os
import time
import json
import math
import random
import pandas as pd
import altair as alt
import streamlit as st
from infoYT import InfoYT, QuotaExceededException
from mongo_operations import MongoOperations
from datetime import datetime, timedelta


# Initialize session state for MongoDB connection status and last attempt time
if 'mongo_connection_active' not in st.session_state:
    st.session_state.mongo_connection_active = False
if 'last_mongo_attempt' not in st.session_state:
    st.session_state.last_mongo_attempt = None

RETRY_COOLDOWN = timedelta(minutes=3)   # Set cooldown period to 5 minutes


# MANAGE MONGODB CONNECTION

@st.cache_resource
def get_mongo_client():
    """
    Create or retrieve a cached MongoDB client.
    """
    return MongoOperations()


def attempt_mongo_connection():
    """
    Attempt to establish a MongoDB connection.
    """
    mongo_client = get_mongo_client()
    connection_success = mongo_client.connect()
    
    st.session_state.mongo_connection_active = connection_success
    st.session_state.last_mongo_attempt = datetime.now()
    
    return mongo_client if connection_success else None


def get_mongo_connection():
    """
    Get MongoDB connection, attempting a new connection if necessary.
    """
    current_time = datetime.now()
    
    # Check if we need to attempt a new connection
    if (not st.session_state.mongo_connection_active and
        (st.session_state.last_mongo_attempt is None or
         current_time - st.session_state.last_mongo_attempt > RETRY_COOLDOWN)):
        return attempt_mongo_connection()
    
    # If we have an active connection, verify it's still valid
    elif st.session_state.mongo_connection_active:
        mongo_client = get_mongo_client()
        try:
            # Attempt a simple operation to verify the connection
            mongo_client.client.admin.command('ismaster')
            return mongo_client
        except Exception:
            # If the operation fails, clear the cache and attempt a new connection
            st.session_state.mongo_connection_active = False
            get_mongo_client.clear()
            return attempt_mongo_connection()
    
    # If we have a failed connection and it's not time to retry, return None
    else:
        return None


def get_existing_channels(mongo_client: MongoOperations) -> list[str]:
    """
    Get the list of existing channel usernames from the database if connected,
    otherwise from the files in the 'Channel_Videos' folder.
    This function is cached to improve performance.
    """
    channels = []

    # Try to get channels from MongoDB if the connection is active
    if st.session_state.mongo_connection_active:
        try:
            channels = [channel['channel_username'] for channel in mongo_client.get_all_channels()]
        except Exception as e:
            st.warning(f"Error fetching channels from MongoDB: {e}")
    
    # If MongoDB failed or is not connected, try to get channels from JSON files
    if not channels:
        folder_path = 'Channel_Videos'
        if os.path.exists(folder_path):
            files = os.listdir(folder_path)
            channels = [f.replace('_videos.json', '') for f in files if f.endswith('_videos.json')]
            if not channels:
                st.warning("No channels found in local JSON files.")
        else:
            st.warning("Channel_Videos folder not found.")

    return sorted(channels)


def get_video_url(channel_username: str, mongo_client: MongoOperations = None) -> str:
    """
    Get the URL of a random video from a channel.
    """
    if mongo_client:
        videos = mongo_client.get_all_videos(channel_username)
        if videos:
            video = random.choice(videos)
            return f"https://www.youtube.com/watch?v={video['_id']}"
    
    # Fallback to JSON file if MongoDB fails or is not available
    filename = f"{channel_username}_videos.json"
    folder_path = 'Channel_Videos'
    file_path = os.path.join(folder_path, filename)
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            videos_dict = json.load(f)
        video_ids = list(videos_dict.keys())
        random_id = random.choice(video_ids)
        return f"https://www.youtube.com/watch?v={random_id}"
    
    return None


def create_upload_frequency_chart(df: pd.DataFrame) -> alt.Chart:
    """
    Create a chart showing the upload frequency of videos over time.
    :param df: DataFrame with video data
    """
    df['published_at'] = pd.to_datetime(df['published_at']).dt.tz_localize(None)
    chart_df = df.groupby(df['published_at'].dt.to_period('M').astype(str)).size().reset_index()
    chart_df.columns = ['date', 'count']
    chart_df['date'] = pd.to_datetime(chart_df['date'])
    chart_df['year'] = chart_df['date'].dt.year
    chart_df['month'] = chart_df['date'].dt.strftime('%b')

    date_range = (chart_df['date'].max() - chart_df['date'].min()).days
    bar_width = max(1, int(600 / len(chart_df)))

    max_count = chart_df['count'].max()
    y_max = math.ceil(max_count * 1.1)  # 10% higher than max, rounded up

    # Determine appropriate tick count and format based on date range
    if date_range <= 365:
        tick_count = 'month'
        date_format = '%b %Y'
    elif date_range <= 365 * 2:
        tick_count = {"interval":"month", "step": 3}
        date_format = '%b %Y'
    else:
        tick_count = 'year'
        date_format = '%Y'

    base = alt.Chart(chart_df).encode(
        x=alt.X('date:T', 
                axis=alt.Axis(
                    format=date_format,
                    labelAngle=-45,
                    title=None,
                    labelPadding=10,  # Increase space for labels
                    labelBaseline='top',  # Place labels below tick marks
                    tickSize=0,  # Remove tick marks
                    tickCount=tick_count
                ),
                scale=alt.Scale(nice=False)
        ),
        y=alt.Y('count:Q', 
                axis=alt.Axis(title='Number of Videos'),
                scale=alt.Scale(domain=[0, y_max])
        ),
        color=alt.Color('year:O', 
                        scale=alt.Scale(scheme='viridis'),
                        legend=alt.Legend(title="Year")
        )
    )

    bars = base.mark_bar(width=bar_width).encode(
        tooltip=[
            alt.Tooltip('yearmonth(date):T', title='Date', format='%B %Y'),
            alt.Tooltip('count:Q', title='Videos', format='d')
        ]
    )

    # We'll remove the year labels since they're now included in the x-axis

    chart = bars.properties(
        width=600,
        height=400
    ).configure_view(
        strokeWidth=0
    ).configure_axis(
        labelFontSize=12,
        titleFontSize=14
    )

    return chart


def initialize_info_yt(url: str, data_source: str, mongo_client: MongoOperations) -> InfoYT:
    """
    Initialize InfoYT object, trusting its internal logic for data source handling and fallback.
    """
    try:
        info_yt = InfoYT(url, data_source=data_source, mongo_client=mongo_client)
        
        if info_yt.db_connected and info_yt.all_videos:

            #with st.empty():
            #    st.success(f"Loaded {len(info_yt.all_videos)} videos from MongoDB.")
            #    time.sleep(3)  # wait for 3 seconds

            st.info(f"Loaded {len(info_yt.all_videos)} videos from MongoDB.")  
        elif info_yt.all_videos:
            st.info(f"Loaded {len(info_yt.all_videos)} videos from local JSON.")
        else:
            st.info("No existing data found. A new channel will be initialized.")

        return info_yt

    except Exception as e:
        st.error(f"Error initializing InfoYT: {str(e)}")
        return None


def main():
    st.set_page_config(layout="wide", page_title="YouTube Channel Analyzer")
    
    st.title("YouTube Channel Analyzer")

    # Data source selection
    data_source = st.radio("Select data source:", ("MongoDB", "Local JSON"))

    # Get or create the MongoDB connection
    mongo_client = get_mongo_connection()

    # Check MongoDB connection status and display appropriate message
    if data_source == "MongoDB":
        if mongo_client is None:
            st.error("Failed to connect to MongoDB. Please switch to Local JSON or check your connection.")

            # Display last attempt time and offer manual retry
            if st.session_state.last_mongo_attempt:
                st.info(f"Last connection attempt: {st.session_state.last_mongo_attempt.strftime('%Y-%m-%d %H:%M:%S')}")

                # Calculate time until next automatic retry
                time_until_retry = (st.session_state.last_mongo_attempt + RETRY_COOLDOWN) - datetime.now()
                if time_until_retry > timedelta(0):
                    st.info(f"Next automatic retry in: {time_until_retry}")
                else:
                    st.info("Automatic retry is due. Refreshing the page will trigger a new connection attempt.")

            if st.button("Retry MongoDB Connection"):
                # Clear the cache and force a new connection attempt
                get_mongo_client.clear()
                mongo_client = attempt_mongo_connection()   # Trigger a new connection attempt

                if mongo_client:
                    st.success("Successfully connected to MongoDB!")
                    st.experimental_rerun()
                else:
                    st.error("Connection attempt failed. Please check your MongoDB setup and try again.")

        else:
            st.success("Connected to MongoDB successfully!")

        # If there's no connection, stop further execution
        if mongo_client is None:
            st.stop()
        
        

    col1, col2 = st.columns(2)

    with col1:
        new_channel_url = st.text_input("Enter a YouTube URL")
    
    with col2:
        existing_channels = get_existing_channels(mongo_client)
        selected_channel = st.selectbox("Or select an existing channel", [""] + existing_channels)

    if new_channel_url or selected_channel:
        if new_channel_url and selected_channel:
            st.warning("Please select only one option.")
            return

        try:
            url = new_channel_url if new_channel_url else get_video_url(selected_channel, mongo_client)
            info_yt = initialize_info_yt(url, data_source, mongo_client)

            if info_yt:
                st.header('Channel Information')
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Channel Name", info_yt.channel_username)
                with col2:
                    st.metric("Total Published Videos", info_yt.num_videos)
                with col3:
                    stored_videos = len(info_yt.all_videos) if info_yt.all_videos is not None else 0
                    st.metric("Stored Videos", stored_videos)

                st.subheader('Actions')
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("Sync Videos"):
                        try:
                            info_yt.sync_videos()
                            info_yt.save_data()     # Save after syncing
                            st.success("Videos synchronized, updated, and saved!")
                        except QuotaExceededException:
                            st.warning("API quota exceeded. Sync is incomplete.")
                        except Exception as e:
                            st.error(f"An error occurred during synchronization: {str(e)}")

                with col2:
                    if st.button("Download All Video Data"):
                        if info_yt.all_videos is None or len(info_yt.all_videos) == 0:
                            try:
                                with st.spinner("Downloading video data... This may take a while."):
                                    info_yt.populate_video_data()
                                    info_yt.save_data()
                                st.success("All video data downloaded and saved!")
                            except QuotaExceededException:
                                st.warning("API quota exceeded. Download is incomplete.")
                            except Exception as e:
                                st.error(f"An error occurred during download: {str(e)}")
                                st.error("Please check the logs for more details.")
                        else:
                            st.info("Video data already exists. Use 'Sync Videos' to update.")

                st.subheader('Stored Videos')
                if st.checkbox("Display stored videos"):
                    df = info_yt.get_videos_dataframe()

                    if not df.empty:
                        # Improved layout for search and pagination
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            search_term = st.text_input("Search videos by title", key="search")
                        with col2:
                            page_size = st.selectbox("Videos per page", [10, 20, 50], key="page_size")
                        with col3:
                            total_pages = len(df) // page_size + (1 if len(df) % page_size > 0 else 0)
                            page_number = st.number_input("Page", min_value=1, max_value=total_pages, value=1, key="page_number", format="%d")
                        
                        # Filter and paginate the dataframe
                        if search_term:
                            df = df[df['title'].str.contains(search_term, case=False)]
                        
                        start_idx = (page_number - 1) * page_size
                        end_idx = start_idx + page_size
                        
                        st.dataframe(df.iloc[start_idx:end_idx], use_container_width=True)

                        # Improved chart
                        st.subheader("Video Upload Frequency")
                        chart = create_upload_frequency_chart(df)
                        # Display the chart
                        st.altair_chart(chart, use_container_width=True)

                        # Export functionality
                        if st.button("Export to CSV"):
                            df.to_csv("video_data.csv", index=False)
                            st.success("Data exported to video_data.csv")
                    else:
                        st.write("No videos stored for this channel.")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Please check the logs for more details.")

if __name__ == "__main__":
    main()