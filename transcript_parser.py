import re
from storage import SQLiteStorage
from typing import List, Dict, Union

class TranscriptParser:
    """
    A class to parse and handle WebVTT (.vtt) transcript files.

    The parser is initialized with the full string content of a VTT file
    and provides methods to extract and manipulate the transcript data.
    """

    def __init__(self, vtt_content: str, storage: SQLiteStorage):
        """
        Initializes the TranscriptParser with the VTT file content.

        :param vtt_content: The full string content of the VTT file.
        :param storage: An instance of SQLiteStorage to access video and chapter data.
        :raises ValueError: If the content is empty or does not appear to be a valid VTT format.
        """
        if not vtt_content or not isinstance(vtt_content, str):
            raise ValueError("VTT content must be a non-empty string.")
        
        content_check = vtt_content.strip()
        if not content_check.upper().startswith('WEBVTT'):
            raise ValueError("Content does not appear to be a valid VTT file (must start with 'WEBVTT').")

        self.content = vtt_content
        self.storage = storage

    def get_plain_text(self) -> str:
        """
        Extracts pure, concatenated text from the VTT content, removing all metadata.
        This method handles YouTube's specific VTT format, including overlapping cues
        and inline word-level timestamps, to produce a single block of clean text.

        :return: A string containing the plain text transcript.
        """
        lines = self.content.split('\n')
        text_parts = []
        seen_lines = set()  # Track lines we've already added to avoid duplicates from overlapping cues

        for line in lines:
            line = line.strip()

            # Skip empty lines and metadata headers
            if not line or '-->' in line or line.upper().startswith(('WEBVTT', 'KIND:', 'LANGUAGE:', 'NOTE')):
                continue

            # Skip sound descriptions like [Music], [Applause]
            if re.match(r'^\[.*\]$', line):
                continue

            # Remove inline word-level timestamps, e.g., <00:00:02.320>
            line = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', line)

            # Remove all other HTML-like tags (e.g., <c>, <i>, <b>)
            line = re.sub(r'<[^>]+>', '', line)

            # Normalize whitespace
            line = ' '.join(line.split())

            # Add the cleaned line if it contains text and has not been seen before
            if line and line not in seen_lines:
                text_parts.append(line)
                seen_lines.add(line)

        if not text_parts:
            return ""

        # Join all parts and normalize whitespace for the final result
        result = ' '.join(text_parts)
        return ' '.join(result.split())

    def _vtt_time_to_seconds(self, time_str: str) -> float:
        """Converts a VTT timestamp string (HH:MM:SS.mmm or MM:SS.mmm) to seconds."""
        parts = time_str.split(':')
        h, m, s_ms = (['0'] * (3 - len(parts))) + parts  # Pad with hours if missing

        s_parts = s_ms.split('.')
        s = s_parts[0]
        ms_str = s_parts[1] if len(s_parts) > 1 else '0'
        
        # Pad milliseconds to 3 digits (e.g., '5' -> '500')
        ms_str = ms_str.ljust(3, '0')
        ms = int(ms_str)

        return int(h) * 3600 + int(m) * 60 + int(s) + ms / 1000

    def get_cues(self) -> List[Dict[str, Union[float, str]]]:
        """
        Parses the VTT content into a structured list of timed cues.
        Each cue is a dictionary containing start time, end time, and cleaned text.
        This method is robust to format variations and handles overlapping text.

        :return: A list of cue dictionaries.
        """
        blocks = self.content.strip().split('\n\n')
        cues = []
        
        for block in blocks:
            lines = block.split('\n')
            if not lines:
                continue

            # Find the line with the timestamp
            time_line_index = -1
            for i, line in enumerate(lines):
                if '-->' in line:
                    time_line_index = i
                    break
            
            if time_line_index == -1:
                continue

            try:
                start_str, end_str = lines[time_line_index].split('-->')
                start_time = self._vtt_time_to_seconds(start_str.strip())
                end_time = self._vtt_time_to_seconds(end_str.strip().split(' ')[0]) # Ignore alignment settings
            except ValueError:
                continue # Skip malformed timestamp lines

            # The text is all subsequent lines
            text_lines = lines[time_line_index + 1:]
            raw_text = ' '.join(text_lines).strip()

            # Clean the text
            cleaned_text = re.sub(r'<\d{2}:\d{2}:\d{2}\.\d{3}>', '', raw_text)
            cleaned_text = re.sub(r'<[^>]+>', '', cleaned_text)
            cleaned_text = re.sub(r'^\[.*\]$', '', cleaned_text)
            cleaned_text = ' '.join(cleaned_text.split())

            if cleaned_text:
                cues.append({
                    'start': start_time,
                    'end': end_time,
                    'text': cleaned_text
                })

        # Post-process to handle YouTube's overlapping text for scrolling effect
        if not cues:
            return []

        processed_cues = []
        if cues:
            processed_cues.append(cues[0])
            for i in range(1, len(cues)):
                current = cues[i]
                previous = processed_cues[-1]   # Compare with processed cues

                # Check if this is a duplicate transition cue (same text, starts within 100ms of previous end)
                if (current['text'] == previous['text'] and 
                    abs(current['start'] - previous['end']) < 0.1):
                    # Merge by extending the previous cue's end time
                    processed_cues[-1]['end'] = current['end']
                else:
                    # Handle scrolling overlaps (new text contains old text)
                    new_cue = current.copy()
                    prev_text = processed_cues[-1]['text']
                    curr_text = current['text']
                    if curr_text.startswith(prev_text):
                        new_cue['text'] = curr_text[len(prev_text):].strip()

                    if new_cue['text']:
                        processed_cues.append(new_cue)

        return processed_cues

    def segment_by_chapters(self, video_id: str) -> List[Dict[str, Union[int, str]]]:
        """
        Segments the transcript by video chapters (timestamps).
        If the video has no chapters, it will be artificially split into 10 parts.
        This method is robust to both real chapters from the database and a fallback scenario.

        :param video_id: The ID of the video to process.
        :return: A list of dictionaries, each representing a chapter with its title, 
                 start time, and the corresponding transcript text.
        """
        video_info = self.storage.get_video(video_id)
        if not video_info:
            raise ValueError(f"Video with ID '{video_id}' not found in the database.")

        chapters = self.storage.get_video_timestamps(video_id)
        video_duration = video_info.get('duration', 0)

        # Ensure consistent data structure for chapters, whether real or fallback.
        # The consistent keys will now be 'description' and 'time_seconds' to match DB.
        if not chapters:
            if video_duration <= 0:
                return []
            
            num_parts = 10
            part_duration = video_duration / num_parts
            # Use 'description' and 'time_seconds' for consistency with DB
            chapters = [{
                'description': f'Part {i + 1}/{num_parts}',
                'time_seconds': int(i * part_duration)
            } for i in range(num_parts)]

        # Prepare chapter boundaries
        chapter_boundaries = []
        for i, chap in enumerate(chapters):
            # Use correct keys 'time_seconds' and 'description' from the database/fallback.
            start = chap['time_seconds']
            end = chapters[i+1]['time_seconds'] if i + 1 < len(chapters) else video_duration
            
            chapter_boundaries.append({
                'title': chap['description'], # Map 'description' to 'title' for internal use
                'start': start,
                'end': end,
                'text_parts': []
            })

        cues = self.get_cues()
        if not chapter_boundaries or not cues:
            return []

        # Assign cues to chapters with 1-cue overlap at boundaries
        cue_index = 0
        for chap_idx, chap in enumerate(chapter_boundaries):
            # Find the first cue that belongs to this chapter
            while cue_index < len(cues) and cues[cue_index]['start'] < chap['start']:
                cue_index += 1
            
            # Add previous cue for context (if exists and not first chapter)
            if cue_index > 0:
                chap['text_parts'].append(cues[cue_index - 1]['text'])
            
            # Store the starting position for this chapter
            chapter_start_index = cue_index
            
            # Add all cues that start within this chapter's time range
            while cue_index < len(cues) and cues[cue_index]['start'] < chap['end']:
                chap['text_parts'].append(cues[cue_index]['text'])
                cue_index += 1
            
            # Add next cue for context (if exists and not last chapter)
            if cue_index < len(cues):
                chap['text_parts'].append(cues[cue_index]['text'])
            
            # Reset index to chapter start for next iteration
            # (so each chapter processes from its natural starting point)
            cue_index = chapter_start_index

        # Format the final output
        return [{
            'chapter_title': chap['title'],
            'start_time': chap['start'],
            'text': ' '.join(chap['text_parts']).strip()
        } for chap in chapter_boundaries]
