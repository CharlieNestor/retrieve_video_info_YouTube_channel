# YouTube Channel Video Tracker

## Overview

This project provides a Python-based tool for tracking and managing video information from YouTube channels. The main goal is to retrieve metadata about videos published by a specific channel and store this information in a JSON file that can be regularly updated.

## Features

- Retrieve channel information from a YouTube URL
- Fetch metadata for all videos in a channel
- Store video information in a JSON file for easy access and updates
- Update existing records with new videos
- Streamlit-based web interface for easy interaction

## Why This Project?

As someone who spends a significant amount of time on YouTube, I created this project as a first step towards building more complex applications that utilize YouTube video information. This tool provides a foundation for easily accessing and managing YouTube channel data, which can be invaluable for content analysis, recommendation systems, or other YouTube-related projects.

## File Structure

get_infoYT.py: Contains the main InfoYT class for interacting with the YouTube API and managing video data.
infoYT_streamlit.py: Implements the Streamlit web interface for the application.
Channel_Videos/: Directory where JSON files containing channel video data are stored.
