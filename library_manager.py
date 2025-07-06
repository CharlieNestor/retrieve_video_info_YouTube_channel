import os
import re
import difflib
import subprocess
from typing import Dict, Any, List, Optional

# Dependencies from other modules in this project
from storage import SQLiteStorage

class LibraryManager:
    """
    Manages synchronization between local video files and the database.
    
    Process:
    1. Scan local library for video files
    2. Check for EXACT matches only against database
    3. For unmatched files, search YouTube using title + duration comparison
    4. Update database records with download status and file paths
    """

    def __init__(self, storage: SQLiteStorage, download_dir: str, video_manager=None, downloader=None):
        """
        Initialize the LibraryManager.

        :param storage: SQLiteStorage instance for database operations
        :param download_dir: Primary directory where videos are stored
        :param video_manager: VideoManager instance for processing videos (optional)
        :param downloader: MediaDownloader instance for YouTube searches (optional)
        """
        self.storage = storage
        self.download_dir = download_dir
        self.video_manager = video_manager
        self.downloader = downloader

    
    def _extract_video_duration(self, file_path: str) -> Optional[float]:
        """
        Extract duration from local .mp4 file using ffprobe.
        
        :param file_path: Path to the video file
        :return: Duration in seconds or None if extraction fails
        """
        try:
            result = subprocess.run([
                'ffprobe', '-v', 'quiet', '-show_entries', 
                'format=duration', '-of', 'csv=p=0', file_path
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
            else:
                return None
                
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError, ValueError, FileNotFoundError):
            return None


    def scan_local_library(self, path: Optional[str] = None) -> Dict[str, Any]:
        """
        Step 1: Scan the local library for video files.
        
        Identifies channel folders using pattern: "Channel Name [ChannelID]"
        Catalogs all .mp4 files within each channel folder with their duration.

        :param path: Directory to scan (defaults to download_dir)
        :return: Dictionary mapping channel_id -> {name, videos[]}
        """
        scan_path = path or self.download_dir
        
        if not os.path.exists(scan_path):
            print(f"ERROR: Path '{scan_path}' does not exist.")
            return {}
        
        print(f"Scanning local library: {scan_path}")
        
        library = {}
        total_videos = 0
        channel_pattern = re.compile(r'^(.+) \[([\w-]+)\]$')

        for folder_name in os.listdir(scan_path):
            folder_path = os.path.join(scan_path, folder_name)
            
            # Skip files and hidden folders
            if not os.path.isdir(folder_path) or folder_name.startswith('.'):
                continue

            # Match channel folder pattern
            match = channel_pattern.match(folder_name)
            if not match:
                continue
            
            channel_name = match.group(1).replace('_', ' ')
            channel_id = match.group(2)
            
            # Find all video files in this channel folder
            video_files = []
            for filename in os.listdir(folder_path):
                if filename.lower().endswith('.mp4') and not filename.startswith('.'):
                    file_path = os.path.join(folder_path, filename)
                    title = os.path.splitext(filename)[0]
                    duration = self._extract_video_duration(file_path)
                    
                    video_files.append({
                        'filename': filename,
                        'title': title,
                        'path': file_path,
                        'duration': duration
                    })
                    total_videos += 1
            
            library[channel_id] = {
                'name': channel_name,
                'videos': video_files
            }
        
        print(f"Found {len(library)} channels with {total_videos} total videos")
        return library
    

    def _process_channel_files(self, channel_id: str, channel_data: Dict, db_videos: List[Dict]) -> Dict:
        """
        Processes all local files for a single channel against its database videos.
        
        :param channel_id: The ID of the channel being processed.
        :param channel_data: The local library data for the channel.
        :param db_videos: The list of video records from the database for this channel.
        :return: A dictionary containing lists of 'exact_matches' and 'unknown_files'.
        """
        channel_results = {'exact_matches': [], 'unknown_files': []}
        
        if not db_videos:
            # No videos in DB for this channel - all files are unknown
            for video in channel_data['videos']:
                channel_results['unknown_files'].append({
                    'channel_id': channel_id,
                    'channel_name': channel_data['name'],
                    **video,
                })
            return channel_results

        # Create mapping for O(1) lookup
        db_videos_map = {v['title']: v for v in db_videos}

        for video in channel_data['videos']:
            if video['title'] in db_videos_map:
                # EXACT match found
                matched_video = db_videos_map[video['title']]
                needs_update = (
                    not matched_video.get('downloaded') or
                    matched_video.get('file_path') != video['path']
                )
                
                match_info = {
                    'channel_id': channel_id,
                    'channel_name': channel_data['name'],
                    'local_file': video,
                    'db_video': matched_video,
                    'needs_update': needs_update
                }
                channel_results['exact_matches'].append(match_info)
            else:
                # No exact match - add to unknown files
                channel_results['unknown_files'].append({
                    'channel_id': channel_id,
                    'channel_name': channel_data['name'],
                    **video,
                })
        
        return channel_results

    def check_exact_matches(self, library: Optional[Dict] = None) -> Dict[str, List]:
        """
        Step 2: Check local files against database using EXACT title matching ONLY.
        
        Identifies matches and then updates database records in a separate step.

        :param library: Result from scan_local_library() (will scan if None)
        :return: Dictionary with exact matches and unknown files
        """
        if library is None:
            library = self.scan_local_library()
        
        total_files = sum(len(channel['videos']) for channel in library.values())
        print(f"Checking {total_files} local files for EXACT matches in database...")
        
        all_matches = []
        all_unknowns = []
        
        # --- Phase 1: Analysis ---
        for channel_id, channel_data in library.items():
            # Get all videos for this channel from the database
            db_videos = self.storage.list_channel_videos(channel_id)
            channel_results = self._process_channel_files(channel_id, channel_data, db_videos)
            all_matches.extend(channel_results['exact_matches'])
            all_unknowns.extend(channel_results['unknown_files'])

        # --- Phase 2: Update Database ---
        updated_records = []
        for match in all_matches:
            if match['needs_update']:
                success = self.storage._update_video_download_status(
                    match['db_video']['id'], match['local_file']['path']
                )
                if success:
                    updated_records.append({
                        'video_id': match['db_video']['id'],
                        'title': match['db_video']['title'],
                        'file_path': match['local_file']['path']
                    })
        
        # --- Phase 3: Compile and Report Results ---
        results = {
            'exact_matches': all_matches,
            'unknown_files': all_unknowns,
            'updated_records': updated_records,
            'stats': {
                'total_files': total_files,
                'exact_matches': len(all_matches),
                'unknown_files': len(all_unknowns),
                'records_updated': len(updated_records)
            }
        }
        
        # Print statistics
        stats = results['stats']
        print(f"\nExact match check complete:")
        print(f"  Exact matches: {stats['exact_matches']}/{stats['total_files']}")
        print(f"  Unknown files: {stats['unknown_files']}/{stats['total_files']}")
        print(f"  Records updated: {stats['records_updated']}")
        
        return results
    
    def resolve_unknown_files(self, unknown_files: List[Dict], 
                        title_threshold: float = 0.8, 
                        duration_threshold_seconds: float = 10.0) -> List[Dict]:
        """
        Step 3: Find YouTube video IDs for unknown files using channel + title + duration matching.
        
        :param unknown_files: List of unknown files from check_exact_matches()
        :param title_threshold: Minimum title similarity (0.0-1.0)
        :param duration_threshold_seconds: Maximum duration difference in seconds. This is also used as the scale for scoring.
        :return: List of files with resolved video_ids
        """
        if not self.downloader:
            print("Error: No downloader available for YouTube searches")
            return unknown_files
        
        print(f"Attempting to resolve YouTube IDs for {len(unknown_files)} unknown files...")
        
        # Group files by channel for efficient API usage
        files_by_channel = {}
        for file_info in unknown_files:
            channel_id = file_info['channel_id']
            if channel_id not in files_by_channel:
                files_by_channel[channel_id] = []
            files_by_channel[channel_id].append(file_info)
        
        resolved_files = []
        
        for channel_id, channel_files in files_by_channel.items():
            try:
                # Fetch ALL videos for this specific channel from YouTube
                print(f"Fetching YouTube video list for channel {channel_id}...")
                youtube_videos = self.downloader.get_channel_video_list(channel_id)
                
                if not youtube_videos:
                    print(f"Warning: No videos found on YouTube for channel {channel_id}")
                    # Add files without video_id
                    for file_info in channel_files:
                        file_info['video_id'] = None
                        file_info['match_details'] = {'reason': 'No YouTube videos found for channel.'}
                        resolved_files.append(file_info)
                    continue
                
                # For each unknown file, find the best YouTube match
                for file_info in channel_files:
                    match_result = self._find_best_youtube_match(
                        file_info, youtube_videos, title_threshold, duration_threshold_seconds
                    )
                    
                    file_info['video_id'] = match_result['video_id']
                    file_info['match_details'] = match_result
                    resolved_files.append(file_info)
                    
            except Exception as e:
                print(f"Error processing channel {channel_id}: {e}")
                # Add files without video_id on error
                for file_info in channel_files:
                    file_info['video_id'] = None
                    file_info['match_details'] = {'error': str(e)}
                    resolved_files.append(file_info)
        
        matched_count = sum(1 for f in resolved_files if f.get('video_id'))
        print(f"Resolution complete: Matched {matched_count} of {len(resolved_files)} files.")
        return resolved_files
    
    
        
    def _find_best_youtube_match(self, file_info: Dict, youtube_videos: List[Dict], 
                           title_threshold: float, duration_threshold_seconds: float) -> Dict:
        """
        Find the best YouTube video match using both title similarity and duration comparison.
        
        :param file_info: Local file information including title and duration
        :param youtube_videos: List of YouTube videos from channel API
        :param title_threshold: Minimum title similarity (0.0-1.0)
        :param duration_threshold_seconds: Maximum duration difference in seconds
        :return: Match result dictionary with video_id and match details
        """
        local_title = file_info['title']
        local_duration = file_info.get('duration')
        
        best_match = {
            'video_id': None,
            'title_similarity': 0.0,
            'duration_diff': float('inf'),
            'combined_score': 0.0,
            'youtube_title': None,
            'youtube_duration': None,
            'match_reason': 'No match found'
        }
        
        for video in youtube_videos:
            youtube_title = video.get('title', '')
            youtube_duration = video.get('duration')
            
            # --- Step 1: Title Similarity Filter ---
            # Calculate how similar the local and YouTube titles are.
            title_similarity = difflib.SequenceMatcher(
                None, local_title.lower(), youtube_title.lower()
            ).ratio()
            
            # Immediately discard if title similarity is below the required threshold.
            if title_similarity < title_threshold:
                continue
            
            # --- Step 2: Duration Gatekeeper ---
            # This is a strict filter. If the duration difference is too large,
            # the video is not a candidate, regardless of title similarity.
            duration_diff = float('inf')
            is_duration_plausible = False
            
            if local_duration is not None and youtube_duration is not None:
                duration_diff = abs(local_duration - youtube_duration)
                is_duration_plausible = duration_diff <= duration_threshold_seconds
            else:
                # If one or both durations are missing, we cannot use it as a strict filter.
                # We give it the benefit of the doubt and allow it to pass to the scoring phase.
                duration_diff = 0.0
                is_duration_plausible = True
            
            # Discard if the duration difference is not plausible.
            if not is_duration_plausible:
                continue
            
            # --- Step 3: Combined Scoring ---
            # For candidates that pass the filters, calculate a combined score to find the best one.
            # The score is a weighted average: 80% for title similarity, 20% for duration proximity.
            
            # Only factor in duration proximity if both durations were available.
            if local_duration is not None and youtube_duration is not None:
                # The duration score is normalized using the threshold itself as the scale.
                # A difference of 0s gets a score of 1.0; a difference at the threshold gets 0.0.
                duration_score = max(0.0, 1.0 - (duration_diff / duration_threshold_seconds))
                combined_score = (0.8 * title_similarity) + (0.2 * duration_score)
            else:
                # If duration is unavailable, the score is based only on title similarity.
                combined_score = title_similarity
            
            # --- Step 4: Update Best Match ---
            # If this video has a better score than the previous best, it becomes the new best match.
            if combined_score > best_match['combined_score']:
                best_match = {
                    'video_id': video.get('id'),
                    'title_similarity': title_similarity,
                    'duration_diff': duration_diff,
                    'combined_score': combined_score,
                    'youtube_title': youtube_title,
                    'youtube_duration': youtube_duration,
                    'match_reason': f'Best match (title: {title_similarity:.2f}, duration_diff: {duration_diff:.1f}s)'
                }
        
        # Final validation - ensure we have a reasonable match
        if best_match['video_id'] is None:
            best_match['match_reason'] = f'No match above thresholds (title >= {title_threshold}, duration <= {duration_threshold_seconds}s)'
        
        return best_match
        
    def update_database_from_resolved_files(self, resolved_files: List[Dict]) -> Dict:
        """
        Step 4: Update the database based on the results of the fuzzy-matching resolution.

        This method takes the resolved files, checks their status against the database,
        and performs the necessary actions:
        - Creates new video records for newly discovered videos.
        - Updates existing records that are out of sync.
        - Skips records that are already perfectly synchronized.

        :param resolved_files: The list of files processed by resolve_unknown_files().
        :return: A dictionary summarizing the actions taken.
        """
        if not self.video_manager:
            print("Error: VideoManager is not available. Cannot process new videos.")
            return {}
            
        print(f"Syncing {len(resolved_files)} resolved files with the database...")
        
        stats = {'created': 0, 'updated': 0, 'skipped': 0, 'failed': 0}

        for file_info in resolved_files:
            video_id = file_info.get('video_id')
            local_path = file_info.get('path')

            # Skip if the file could not be matched to a YouTube video
            if not video_id:
                continue

            try:
                # Check if this video already exists in our database
                db_video = self.storage.get_video(video_id)

                if db_video:
                    # --- Scenario A: Video exists in the database ---
                    # Check if the existing record needs to be updated.
                    is_downloaded = db_video.get('downloaded', 0)
                    db_path = db_video.get('file_path', '')

                    if not is_downloaded or db_path != local_path:
                        print(f"Updating existing record for video: {video_id}")
                        self.storage._update_video_download_status(video_id, local_path)
                        stats['updated'] += 1
                    else:
                        # The record is already perfect, no action needed.
                        stats['skipped'] += 1
                
                else:
                    # --- Scenario B: New video discovered ---
                    # 1. Process the video to fetch all metadata and create the record.
                    print(f"Processing new video to database: {video_id}")
                    self.video_manager.process(video_id)
                    
                    # 2. Update the newly created record to mark it as downloaded.
                    print(f"Updating download status for new video: {video_id}")
                    self.storage._update_video_download_status(video_id, local_path)
                    stats['created'] += 1

            except Exception as e:
                print(f"ERROR: Failed to sync video {video_id}. Reason: {e}")
                stats['failed'] += 1
        
        print("\nDatabase synchronization complete.")
        print(f"  Created: {stats['created']}")
        print(f"  Updated: {stats['updated']}")
        print(f"  Skipped: {stats['skipped']}")
        print(f"  Failed:  {stats['failed']}")
        
        return stats
        
