import os
import json
import streamlit as st
from get_infoYT import InfoYT


# Function to get existing channel usernames from files
def get_existing_channels() -> list[str]:
    """
    get the list of existing channel usernames from the files in the 'Channel_Videos' folder.
    """
    folder_path = 'Channel_Videos'
    if not os.path.exists(folder_path):
        return []
    
    files = os.listdir(folder_path)
    channels = [f.replace('_videos.json', '') for f in files if f.endswith('_videos.json')]
    return channels

def get_video_url(channel_username: str) -> str:
    """
    get the URL of the first video of a channel.
    """
    filename = channel_username+'_videos.json'
    folder_path = 'Channel_Videos'
    file_path = os.path.join(folder_path, filename) 
    with open(file_path, 'r') as f:
        videos_dict = json.load(f)
    video_ids = list(videos_dict.keys())
    video_url = f"https://www.youtube.com/watch?v={video_ids[0]}"
    return video_url


def main() -> None:
    """
    main function for the Streamlit app.
    """
    st.title("YouTube Channel Videos App")

    # Input for new channel URL
    new_channel_url = st.text_input("Enter a YouTube URL")

    # Selector for existing channels
    existing_channels = get_existing_channels()
    selected_channel = st.selectbox("Or select an existing channel", [""] + existing_channels)  # add first blank option

    if new_channel_url or selected_channel:
        # Avoid selecting both options (remember that options stay selected in the different sessions)
        if new_channel_url and selected_channel:
            st.warning("Please select only one option.")
            return
        try:
            if new_channel_url:
                info_yt = InfoYT(new_channel_url)
            else:
                # Reconstruct the URL for existing channel
                channel_url = get_video_url(selected_channel)
                info_yt = InfoYT(channel_url)

            st.write('##')
            # Display channel information
            st.write('**CHANNEL INFORMATION:**')
            st.write(f"Channel name: **{info_yt.channel_username}**")
            st.write(f"Total published videos: {info_yt.num_videos}")
            if info_yt.check_history():
                st.write(f'The number of videos already stored is: {len(info_yt.all_videos)}')
            else:
                st.write("No videos stored for this channel.")

            st.write('###')
            # Write a streamlit checkbox to display the stored videos
            display_videos = st.checkbox("Display stored videos")
            if display_videos:
                df = info_yt.get_videos_dataframe()
                if not df.empty:
                    st.write("Stored videos:")
                    st.dataframe(df)
                else:
                    st.write("No videos stored for this channel.")

            st.write('###')
            # Add a streamlit button to update the videos
            st.write('Retrieve and update the dataset with the latest videos:')
            if st.button("Update video "):
                if info_yt.check_history():
                    output = (info_yt.update_videos(streamlit=True))
                    if len(output) > 0:
                        st.write(f"I've found {len(output)} new videos to be added!")
                        for title in output:
                            st.warning(f"New video found: {title}")
                    info_yt.save_to_json()
                    st.success("Videos updated and saved!")
                else:
                    st.warning("No videos stored for this channel. Impossible to update.")  

            st.write('###')
            # Add a streamlit button to download the historical data
            st.write('Download historical data for the channel:')
            if st.button("Download historical data"):
                if not info_yt.check_history():
                    output = info_yt.get_all_videos(max_videos=200, streamlit=True)
                    if len(output) > 0:
                        st.write(f"This download has retrieved {len(output)} videos.")
                    info_yt.save_to_json()
                    st.success("Historic data downloaded and saved!")
                elif len(info_yt.all_videos) < 0.9*info_yt.num_videos:
                    output = info_yt.get_all_videos(max_videos=100, streamlit=True)
                    if len(output) > 0:
                        st.write(f"I've found {len(output)} new videos to be added!")
                    info_yt.save_to_json()
                    st.success("Videos updated and saved!")
                else:
                    st.warning("Historic data already downloaded.") 

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")


if __name__ == "__main__":

    main()
