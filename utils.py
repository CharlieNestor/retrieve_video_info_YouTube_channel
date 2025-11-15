import re
import hashlib
from datetime import datetime
from typing import Union, Optional

# Helper function for sanitizing filenames
def sanitize_filename(name: str) -> str:
    """
    Removes or replaces characters unsafe for filenames.
    :param name: Filename to sanitize
    :return: Sanitized filename or 'untitled'
    """
    # Remove characters that are problematic
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    # Replace sequences of dots or spaces with a single underscore
    name = re.sub(r'\.+', '_', name)
    name = re.sub(r'\s+', '_', name)
    # Ensure it doesn't start/end with problematic chars like space or dot
    name = name.strip(' .')
    # Limit length of the name
    max_len = 200
    if len(name) > max_len:
        name = name[:max_len]
    return name if name else "untitled" # Ensure not empty


def normalize_title_for_comparison(title: str) -> str:
    """
    Normalizes a title for comparison by:
    1. Converting to lowercase
    2. Removing common separators and special characters
    3. Removing common words that might be added/removed in filenames
    
    :param title: Title string to normalize
    :return: Normalized title string
    """
    # Convert to lowercase
    normalized = title.lower()
    
    # Replace underscores with spaces (since sanitize_filename replaces spaces with underscores)
    normalized = normalized.replace('_', ' ')
    
    # Remove special characters and extra spaces
    normalized = re.sub(r'[^\w\s]', '', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    
    # Remove common words that might be added by YouTube or downloaders
    common_words = [
        'official', 'video', 'hd', '4k',
    ]
    
    for word in common_words:
        normalized = normalized.replace(f' {word} ', ' ')
    
    # Remove any leading/trailing common words
    for word in common_words:
        if normalized.startswith(f'{word} '):
            normalized = normalized[len(word)+1:]
        if normalized.endswith(f' {word}'):
            normalized = normalized[:-len(word)-1]
    
    return normalized.strip()


def normalize_vtt_for_hash(vtt: str) -> str:
    """
    Normalizes VTT (WebVTT) content for consistent hashing.
    
    This function ensures that the same transcript content always produces
    the same hash, regardless of platform-specific line endings or trailing
    whitespace variations.
    
    Normalization steps:
    1. Converts all line endings (\r\n, \r) to \n
    2. Removes trailing whitespace from each line (preserves leading whitespace)
    3. Joins lines with consistent \n separator
    
    Leading whitespace is preserved as it may be significant for VTT formatting,
    but trailing whitespace is removed as it's never meaningful and varies by editor.
    
    :param vtt: Raw VTT content string
    :return: Normalized VTT string suitable for hashing
    
    Example:
        >>> vtt = "WEBVTT\r\n\r\n00:00:00.000 --> 00:00:05.000  \nHello world  \n"
        >>> normalized = normalize_vtt_for_hash(vtt)
        >>> # Produces consistent output regardless of input line endings
    """
    if not vtt:
        return ""
    
    # Normalize line endings and remove trailing whitespace from each line
    return '\n'.join(
        line.rstrip() 
        for line in vtt.replace('\r\n', '\n').replace('\r', '\n').split('\n')
    )


def compute_vtt_hash(vtt: str) -> str:
    """
    Computes a SHA-256 hash of normalized VTT content.
    
    This function provides a consistent way to detect changes in transcript content
    across the application. The same transcript will always produce the same hash,
    even if it comes from different sources or has minor formatting differences.
    
    :param vtt: Raw VTT content string
    :return: Hexadecimal SHA-256 hash string (64 characters)
    
    Example:
        >>> vtt = "WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nHello\n"
        >>> hash_value = compute_vtt_hash(vtt)
        >>> len(hash_value)
        64
    """
    normalized = normalize_vtt_for_hash(vtt)
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def format_datetime(upload_date: Optional[str] = None, 
                    timestamp: Optional[int] = None,
                    dt: Optional[datetime] = None) -> Optional[str]:
    """
    Standardized datetime formatter for the application.
    Returns datetime in SQLite CURRENT_TIMESTAMP format: 'YYYY-MM-DD HH:MM:SS'
    
    :param upload_date: Date in YYYYMMDD format (e.g., '20210310') 
                       or ISO format (e.g., '2021-03-10')
    :param timestamp: Unix timestamp in seconds (e.g., 1615358397)
    :param dt: Python datetime object
    :return: Formatted datetime string or None if conversion fails
    """
    try:
        if dt and isinstance(dt, datetime):
            # Use provided datetime object directly
            return dt.strftime('%Y-%m-%d %H:%M:%S')
            
        if timestamp:
            # Use timestamp for full date and time
            dt = datetime.fromtimestamp(timestamp)
            return dt.strftime('%Y-%m-%d %H:%M:%S')
                
        elif upload_date:
            # Handle date-only values
            try:
                # Try standard format YYYYMMDD
                dt = datetime.strptime(upload_date, '%Y%m%d')
                # Return with time set to 00:00:00 for consistency
                return dt.strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                # Try alternative formats
                for fmt in ['%Y-%m-%d', '%Y-%m-%dT%H:%M:%SZ', '%Y-%m-%d %H:%M:%S']:
                    try:
                        dt = datetime.strptime(upload_date, fmt)
                        return dt.strftime('%Y-%m-%d %H:%M:%S')
                    except ValueError:
                        continue
                # If we get here, none of the formats matched
                raise ValueError(f"Unrecognized date format: {upload_date}")
        
        return None
    
    except Exception as e:
        print(f"Error formatting date: {str(e)}")
        return None