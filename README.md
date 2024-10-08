# YouTube Channel Video Tracker


YouTube Channel Video Tracker is a Python-based tool designed to streamline the process of tracking and managing video information from YouTube channels. This project offers an efficient solution for retrieving, storing, and updating metadata about videos published by specific channels, providing a solid foundation for various YouTube-related applications and analyses. 
One possible application of this tool can be seen in the [chat_with_Lex_RAG project](https://github.com/CharlieNestor/chat_with_Lex_RAG), where a Retrieval-Augmented Generation (RAG) system is generated using the transcripts obtained from videos of one specific YouTube channel. 


## Key Features

- **Channel Information Retrieval**: Easily extract channel details from any YouTube URL.
- **Comprehensive Video Metadata**: Fetch and store detailed metadata for all videos in a channel.
- **Synchronization**: Keep your local data up-to-date with the latest channel information.
- **Efficient Data Storage**: Utilize JSON file format and MongoDB for easy access, updates, and portability.
- **User-Friendly Interface**: Interact with the tool through an intuitive Streamlit-based web interface.
- **Data Visualization**: View upload frequency charts and paginated video listings.
- **Docker Support**: Easy deployment and consistent environment using Docker, including MongoDB setup.


## Prerequisites

- YouTube Data API v3
- MongoDB (here we use it via Docker)

## Getting Started

1. Setup your Google Cloud API:
- Create a project in the Google Developers Console (https://console.cloud.google.com/)
- Enable the YouTube Data API v3
- Create credentials (API Key)

2. Clone the repository:
```sh 
git clone https://github.com/CharlieNestor/retrieve_video_info_YouTube_channel.git
```

3. Create a .env file containing your YouTube Data API key and MongoDB credentials (if you choose to run MongoDB via Docker):
```sh
YOUTUBE_API_KEY=your_api_key_here
MONGO_URI=mongodb://admin:password@localhost:27017/
```

4. Install the required packages in a new virtual environment:
```sh
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

5. Run the applications:

### Running MongoDB via Docker
If you choose to run MongoDB via Docker, start the MongoDB container by running in the Terminal:
```sh
docker-compose -f docker_youtube_tracker.yml up -d
```

### Running the Streamlit App
To start the Streamlit app, run the following command in the Terminal:
```sh
streamlit run infoYT_streamlit.py
```

## Usage

1. Enter a YouTube channel URL or select an existing channel from the dropdown.
2. The app retrieves comprehensive channel information, including subscriber count, total views, and channel description.
3. You can sync videos to update the local database with the latest channel and video information.
4. View stored videos in a paginated table, search by title, and visualize upload frequency.
5. Export video data to CSV for further analysis.


## File Structure

- `infoYT.py`: Core functionality for YouTube API interaction and data management.
- `infoYT_jupyter.ipynb`: Jupyter Notebook with usage examples and functionality demonstrations.
- `infoYT_streamlit.py`: Streamlit web interface implementation.
- `mongo_operations.py`: MongoDB operations for data storage and retrieval.
- `logging_config.py`: Configuration for the logging system.
- `docker_youtube_tracker.yml`: Docker Compose configuration for easy deployment.
- `Channel_Videos/`: Storage directory for channel-specific JSON data files.


## Data Storage

1. **MongoDB (Primary)**: Data is stored in a MongoDB database, which can be accessed and managed using the provided Docker setup.
2. **Local JSON (Fallback)**: Channel data is stored in JSON files within the `Channel_Videos/` directory.



