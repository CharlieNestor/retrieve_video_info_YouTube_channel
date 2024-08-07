import os
import json
import math
import random
import pandas as pd
import altair as alt
import streamlit as st
from datetime import timedelta
from infoYT import InfoYT, QuotaExceededException

@st.cache_data
def get_existing_channels() -> list[str]:
    """
    Get the list of existing channel usernames from the files in the 'Channel_Videos' folder.
    """
    folder_path = 'Channel_Videos'
    if not os.path.exists(folder_path):
        return []
    
    files = os.listdir(folder_path)
    channels = [f.replace('_videos.json', '') for f in files if f.endswith('_videos.json')]
    return sorted(channels)

@st.cache_data
def get_video_url(channel_username: str) -> str:
    """
    Get the URL of a random video from a channel.
    """
    filename = f"{channel_username}_videos.json"
    folder_path = 'Channel_Videos'
    file_path = os.path.join(folder_path, filename)
    with open(file_path, 'r') as f:
        videos_dict = json.load(f)
    video_ids = list(videos_dict.keys())
    random_id = random.choice(video_ids)
    return f"https://www.youtube.com/watch?v={random_id}"


def create_upload_frequency_chart(df):
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

    base = alt.Chart(chart_df).encode(
        x=alt.X('date:T', 
                axis=alt.Axis(
                    format='%b',
                    labelAngle=-45,
                    title=None,
                    labelPadding=10,  # Increase space for labels
                    labelBaseline='top',  # Place labels below tick marks
                    tickSize=0  # Remove tick marks
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

    # Add year labels below the x-axis
    year_labels = alt.Chart(chart_df).mark_text(
        align='center', 
        baseline='bottom', 
        dy=30  # Adjust this value to position the year labels
    ).encode(
        x='date:T',
        text='year:O',
        opacity=alt.condition(
            alt.datum.month == 'Jan',  # Only show label for January
            alt.value(1),
            alt.value(0)
        )
    )

    chart = (bars + year_labels).properties(
        width=600,
        height=400
    ).configure_view(
        strokeWidth=0
    ).configure_axis(
        labelFontSize=12,
        titleFontSize=14
    )

    return chart


def create_upload_frequency_chart(df):
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
        tick_count = 'quarter'
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



def main():
    st.set_page_config(layout="wide", page_title="YouTube Channel Analyzer")
    
    st.title("YouTube Channel Analyzer")

    col1, col2 = st.columns(2)

    with col1:
        new_channel_url = st.text_input("Enter a YouTube URL")
    
    with col2:
        existing_channels = get_existing_channels()
        selected_channel = st.selectbox("Or select an existing channel", [""] + existing_channels)

    if new_channel_url or selected_channel:
        if new_channel_url and selected_channel:
            st.warning("Please select only one option.")
            return

        try:
            if new_channel_url:
                info_yt = InfoYT(new_channel_url)
            else:
                channel_url = get_video_url(selected_channel)
                info_yt = InfoYT(channel_url)

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
                        info_yt.save_to_json()  # Save after syncing
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
                                info_yt.save_to_json()
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