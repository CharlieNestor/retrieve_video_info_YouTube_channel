# YouTube Channel Video Tracker

## Overview

YouTube Channel Video Tracker is a powerful Python-based tool designed to streamline the process of tracking and managing video information from YouTube channels. This project offers an efficient solution for retrieving, storing, and updating metadata about videos published by specific channels, providing a solid foundation for various YouTube-related applications and analyses. Whether you're a content creator, a data analyst, or a YouTube enthusiast, this tool provides valuable insights and data management capabilities in the universe of YouTube content.


## Key Features

- **Channel Information Retrieval**: Easily extract channel details from any YouTube URL.
- **Comprehensive Video Metadata**: Fetch and store detailed metadata for all videos in a channel.
- **Synchronization**: Keep your local data up-to-date with the latest channel information.
- **Efficient Data Storage**: Utilize JSON file format and MongoDB for easy access, updates, and portability.
- **User-Friendly Interface**: Interact with the tool through an intuitive Streamlit-based web interface.
- **Flexible API Integration**: Built on the YouTube Data API v3 for reliable and up-to-date information.
- **Data Visualization**: View upload frequency charts and paginated video listings.
- **Logging**: Comprehensive logging system for better debugging and monitoring.
- **Docker Support**: Easy deployment and consistent environment using Docker, including MongoDB setup.


## Usage

### Setup
- Install Docker on your system
- Create a project in the Google Developers Console
- Enable the YouTube Data API v3
- Create credentials (API Key)
- Create a .env file in the project root and add your API key:
```sh
YOUTUBE_API_KEY=your_api_key_here
MONGO_HOST=mongo
MONGO_PORT=27017
MONGO_USERNAME=admin
MONGO_PASSWORD=password
MONGO_DB=youtube_tracker
```

### Running MongoDB via Docker
Start the MongoDB container by running in the Terminal:
```sh
docker-compose up -d
```

### Running the Streamlit App
To start the Streamlit app, run the following command in the Terminal:
```sh
streamlit run infoYT_streamlit.py
```

## File Structure

- `infoYT.py`: Core functionality for YouTube API interaction and data management.
- `infoYT_jupyter.ipynb`: Jupyter Notebook with usage examples and functionality demonstrations.
- `infoYT_streamlit.py`: Streamlit web interface implementation.
- `mongo_operations.py`: MongoDB operations for data storage and retrieval.
- `logging_config.py`: Configuration for the logging system.
- `docker-compose.yml`: Docker Compose configuration for easy deployment.
- `Channel_Videos/`: Storage directory for channel-specific JSON data files.

## How it Works

1. Enter a YouTube channel URL or select an existing channel from the dropdown.
2. The app retrieves comprehensive channel information, including subscriber count, total views, and channel description.
3. You can sync videos to update the local database with the latest channel and video information.
4. View stored videos in a paginated table, search by title, and visualize upload frequency.
5. Export video data to CSV for further analysis.

## Data Storage

1. **MongoDB (Primary)**: Data is stored in a MongoDB database, which can be accessed and managed using the provided Docker setup.
2. **Local JSON (Fallback)**: Channel data is stored in JSON files within the `Channel_Videos/` directory.



