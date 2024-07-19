# YouTube Channel Video Tracker

## Overview

YouTube Channel Video Tracker is a powerful Python-based tool designed to streamline the process of tracking and managing video information from YouTube channels. This project offers an efficient solution for retrieving, storing, and updating metadata about videos published by specific channels, providing a solid foundation for various YouTube-related applications and analyses.

## Why This Project?

In the ever-expanding universe of YouTube content, staying on top of channel activities and video releases can be challenging. This project was born out of a passion for YouTube and a desire to create a robust foundation for more complex YouTube-centric applications. Whether you're a content creator, a data analyst, or a YouTube enthusiast, this tool provides valuable insights and data management capabilities.

## Key Features

- **Channel Information Retrieval**: Easily extract channel details from any YouTube URL.
- **Comprehensive Video Metadata**: Fetch and store detailed metadata for all videos in a channel.
- **Efficient Data Storage**: Utilize JSON file format for easy access, updates, and portability.
- **User-Friendly Interface**: Interact with the tool through an intuitive Streamlit-based web interface.
- **Flexible API Integration**: Built on the YouTube Data API v3 for reliable and up-to-date information.


## Usage

### Setup
- Create a project in the Google Developers Console
- Enable the YouTube Data API v3
- Create credentials (API Key)
- Create a .env file in the project root and add your API key:
```sh
YOUTUBE_API_KEY=your_api_key_here
```

### Running the Streamlit App
To start the Streamlit app, run the following command in the Terminal:
```sh
streamlit run ticker_streamlit.py
```

## File Structure

- `get_infoYT.py`: Core functionality for YouTube API interaction and data management.
- `infoYT_jupyter.ipynb`: Jupyter Notebook with usage examples and functionality demonstrations.
- `infoYT_streamlit.py`: Streamlit web interface implementation.
- `Channel_Videos/`: Storage directory for channel-specific JSON data files.
