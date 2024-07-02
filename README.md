# YouTube Channel Video Tracker

## Overview

This project provides a Python-based tool for tracking and managing video information from YouTube channels. The main goal is to retrieve metadata about videos published by a specific channel and store this information in a JSON file that can be regularly updated.

## Why This Project?

As someone who spends a significant amount of time on YouTube, I created this project as a first step towards building more complex applications that utilize YouTube video information. This tool provides a foundation for easily accessing and managing YouTube channel data, which can be invaluable for content analysis, recommendation systems, or other YouTube-related projects.


## Features

- Retrieve channel information from a YouTube URL
- Fetch metadata for all videos in a channel
- Store video information in a JSON file for easy access and updates
- Update existing records with new videos
- Streamlit-based web interface for easy interaction


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

*get_infoYT.py*: \
Contains the main InfoYT class for interacting with the YouTube API and managing video data. \
*infoYT_jupyter.ipynb*: \
Jupyter Notebook showing example of usage of the methods in the InfoYT class. Useful to get familiar with the functionalities. \
*infoYT_streamlit.py*: \
Implements the Streamlit web interface for the application. \
*Channel_Videos/*: \
Directory where JSON files containing channel video data are stored.
