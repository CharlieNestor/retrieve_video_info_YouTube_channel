import os
import time
from typing import Dict, List, Optional

# Try to import Google AI, but don't crash if missing
try:
    from google import genai 
except Exception:
    genai = None

# Configuration constants
MODEL_NAME = "gemini-2.5-flash"
MAX_HISTORY_CHARS = 50_000
SESSION_TIMEOUT_SECONDS = 1_800      # 30 minutes
MAX_CHAPTER_SUMMARY_CHARS = 350
COOLDOWN_SECONDS = 5


class ChatSession:
    """
    Keeps track of one conversation about a video.

    Lifecycle:
    - A session is strictly tied to a single video_id.
    - It remains active until it times out (SESSION_TIMEOUT_SECONDS).
    - If the same session_id is used to ask about a DIFFERENT video, 
      this session object is replaced (history is lost).
    - If a different session_id is used, this instance remains in memory 
      until it expires.
    
    Attributes:
    - video_id: which video we're talking about
    - history: list of messages [{role: 'user/assistant', content: 'text'}]
    - last_used: when was this session last active (for cleanup)
    - summary: compressed version of old messages (when history gets too long)
    - chapter_summaries: list of dicts with chapter info (generated once per session)
    """
    
    def __init__(self, video_id: str):
        self.video_id = video_id
        self.history = []   # Recent messages
        self.summary = ""   # Compressed old messages
        self.chapter_summaries = None   # Will be generated on first ask
        self.last_used = time.time()
    
    def update_timestamp(self):
        """Mark this session as recently used."""
        self.last_used = time.time()
    
    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if this session has been inactive too long."""
        return (time.time() - self.last_used) > ttl_seconds


class LLMService:
    """
    Allows users to ask questions about YouTube video transcripts using AI.
    
    How it works:
    1. User asks a question about a video
    2. We fetch the video's transcript
    3. We send transcript + question + previous conversation to AI
    4. AI answers based on the transcript
    5. We remember the conversation for follow-up questions
    
    When conversations get long, we compress old messages into a summary
    to save memory and API costs.
    """
    
    def __init__(self, video_manager):
        """
        Initialize LLM service for asking questions about video transcripts
        
        :param video_manager: Object that can fetch video transcripts and chapters
        """
        self.video_manager = video_manager
        self.model_name = MODEL_NAME
        self.max_history_chars = MAX_HISTORY_CHARS
        self.session_timeout_seconds = SESSION_TIMEOUT_SECONDS
        self.cooldown_seconds = COOLDOWN_SECONDS
        
        api_key = os.getenv("GOOGLE_API_KEY")
        self.enabled = bool(api_key and genai)
        self.client = genai.Client(api_key=api_key) if self.enabled else None
        
        # In-memory storage
        self.sessions: Dict[str, ChatSession] = {}      # session_id -> ChatSession
        self.last_request_time: Dict[str, float] = {}   # session_id -> timestamp (for rate limiting)
    

    def ask(self, video_id: str, session_id: str, question: str, lang: Optional[str] = None) -> dict:
        """
        Ask a question about a video's transcript
        
        :param video_id: YouTube video ID
        :param session_id: Unique session identifier (keeps conversation history)
        :param question: User's question
        :param lang: Optional language code for transcript
        :return: Dict with answer or error message
        """
        if not question or not question.strip():
            return {"error": "Question cannot be empty"}
        
        if not self.enabled:
            return {"error": "LLM service not configured. Set GOOGLE_API_KEY in environment."}
        
        # Clean up old sessions
        self._delete_expired_sessions()
        
        # Rate limiting: prevent spam
        if not self._check_cooldown(session_id):
            return {"error": "Too many requests. Please wait a moment."}
        
        # Get or create session
        session = self._get_or_create_session(session_id, video_id)
        
        # If user switched to a different video, reset the session
        if session.video_id != video_id:
            session = ChatSession(video_id)
            self.sessions[session_id] = session
        
        # Fetch the transcript
        transcript = self.video_manager.get_transcript_plain(video_id, lang)
        if not transcript:
            return {"error": f"No transcript available for video {video_id}"}
        
        # Generate chapter summaries if not already done
        if session.chapter_summaries is None:
            session.chapter_summaries = self._generate_chapter_summaries(video_id, lang, transcript)
        
        # Build the prompt
        chapters = self._format_chapter_summaries(session.chapter_summaries)
        history_text = self._format_conversation_history(session)
        prompt = self._build_prompt(question, transcript, chapters, history_text)
        
        # Call the AI
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            answer = response.text.strip() if hasattr(response, 'text') else ""
        except Exception as e:
            return {"error": f"AI service error: {str(e)}"}
        
        # Save to history
        session.history.append({"role": "user", "content": question.strip()})
        session.history.append({"role": "assistant", "content": answer})
        session.update_timestamp()
        
        # If history is getting too long, compress it
        did_summarize = False
        if self._count_history_chars(session) > self.max_history_chars:
            summary = self._create_summary(session, transcript)
            if summary:
                session.summary = summary
                session.history = session.history[-2:]  # Keep only last question/answer
                did_summarize = True
        
        return {
            "answer": answer,
            "video_id": video_id,
            "session_id": session_id,
            "summarized": did_summarize
        }
    
    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        """
        Retrieve the conversation history for a session.
        
        :param session_id: Unique session identifier
        :return: List of message dicts
        """
        if session_id in self.sessions:
            return self.sessions[session_id].history
        return []
    
    def end_session(self, session_id: str):
        """
        Delete a session and its history
        
        :param session_id: Session identifier to delete
        """
        self.sessions.pop(session_id, None)
        self.last_request_time.pop(session_id, None)

    
    def _get_or_create_session(self, session_id: str, video_id: str) -> ChatSession:
        """
        Get existing session or create new one
        
        :param session_id: Unique session identifier
        :param video_id: YouTube video ID
        :return: ChatSession object
        """
        if session_id not in self.sessions:
            self.sessions[session_id] = ChatSession(video_id)
        return self.sessions[session_id]
    
    def _check_cooldown(self, session_id: str) -> bool:
        """
        Rate limiting: ensure user waits between requests.
        Returns True if request is allowed, False if too soon.
        """
        now = time.time()
        last_request = self.last_request_time.get(session_id, 0)
        
        if now - last_request < self.cooldown_seconds:
            return False
        
        self.last_request_time[session_id] = now
        return True
    
    def _delete_expired_sessions(self):
        """
        Remove old inactive sessions to prevent memory leaks
        """
        expired = [
            sid for sid, session in self.sessions.items()
            if session.is_expired(self.session_timeout_seconds)
        ]
        for sid in expired:
            self.end_session(sid)
    
    def _generate_chapter_summaries(self, video_id: str, lang: Optional[str], transcript: str) -> List[Dict]:
        """
        Generate AI summaries for each chapter (done once per session)
        
        :param video_id: YouTube video ID
        :param lang: Optional language code
        :param transcript: Full video transcript
        :return: List of dicts with chapter info and summaries
        """
        try:
            segments = self.video_manager.get_transcript_by_chapters(video_id, lang) or []
        except Exception:
            segments = []
        
        if not segments or not self.enabled:
            return []
        
        # Build structure with start/end times
        chapters = []
        for i, seg in enumerate(segments):
            title = seg.get("chapter_title") or seg.get("title") or f"Chapter {i+1}"
            start = seg.get("start_time")
            text = seg.get("text") or ""
            
            # End time is start of next chapter, or None for last
            end = segments[i+1].get("start_time") if i+1 < len(segments) else None
            
            chapters.append({
                "title": title,
                "start": start,
                "end": end,
                "text": text
            })
        
        # Ask LLM to summarize all chapters at once
        chapters_text = "\n\n".join([
            f"Chapter: {ch['title']} ({ch['start']}s - {ch['end'] or 'end'}s)\nText: {ch['text']}"
            for ch in chapters
        ])
        
        prompt = f"""
            Summarize each chapter below in maximum {MAX_CHAPTER_SUMMARY_CHARS} characters each.
            Keep it factual and concise. Format as: "Chapter Title: summary here"

            {chapters_text}
            """
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            summaries_text = response.text.strip() if hasattr(response, 'text') else ""
            
            # Parse the response and add summaries to chapters
            summary_lines = [line.strip() for line in summaries_text.split('\n') if line.strip()]
            for i, ch in enumerate(chapters):
                if i < len(summary_lines):
                    # Extract summary after colon if present
                    summary = summary_lines[i].split(':', 1)[-1].strip()
                    ch['summary'] = summary[:MAX_CHAPTER_SUMMARY_CHARS]
                else:
                    ch['summary'] = ""
                # Remove text to save memory
                del ch['text']
            
            return chapters
        except Exception:
            # If summarization fails, return chapters without summaries
            for ch in chapters:
                ch['summary'] = ""
                del ch['text']
            return chapters
    
    def _format_chapter_summaries(self, chapter_summaries: List[Dict]) -> str:
        """
        Format chapter summaries for inclusion in prompt
        
        :param chapter_summaries: List of chapter dicts with summaries
        :return: Formatted string
        """
        if not chapter_summaries:
            return "No chapters available."
        
        lines = []
        for ch in chapter_summaries:
            end_str = f"{ch['end']}s" if ch['end'] is not None else "end"
            if ch['summary']:
                lines.append(f"- {ch['title']} ({ch['start']}s - {end_str}): {ch['summary']}")
            else:
                lines.append(f"- {ch['title']} ({ch['start']}s - {end_str})")
        
        return "\n".join(lines)
    
    def _format_conversation_history(self, session: ChatSession) -> str:
        """
        Format conversation history for AI prompt including summary and recent messages
        
        :param session: ChatSession object
        :return: Formatted conversation history string
        """
        if not session.summary and not session.history:
            return "No previous conversation."
        
        parts = []
        
        # Add summary if exists
        if session.summary:
            parts.append("=== Summary of Earlier Conversation ===")
            parts.append(session.summary)
            parts.append("\n=== Recent Messages ===")
        
        # Add recent messages (walk backwards to get most recent within budget)
        budget = self.max_history_chars
        recent_messages = []
        char_count = 0
        
        for msg in reversed(session.history):
            line = f"{msg['role'].upper()}: {msg['content']}"
            if char_count + len(line) > budget:
                break
            recent_messages.insert(0, line)
            char_count += len(line)
        
        if recent_messages:
            parts.extend(recent_messages)
        
        return "\n".join(parts)
    
    def _count_history_chars(self, session: ChatSession) -> int:
        """
        Count total characters in session history for compression check
        
        :param session: ChatSession object
        :return: Total character count
        """
        total = len(session.summary)
        for msg in session.history:
            total += len(msg.get("content", ""))
        return total
    
    def _build_prompt(self, question: str, transcript: str, chapters: str, history: str) -> str:
        """
        Build complete prompt to send to AI
        
        :param question: User's question
        :param transcript: Video transcript text
        :param chapters: Formatted chapter overview
        :param history: Formatted conversation history
        :return: Complete prompt string
        """
        return f"""
        You are helping a user understand a YouTube video by answering questions about its transcript.

        RULES:
        - Base your answers on the transcript provided below
        - If something isn't in the transcript, say you can't find it
        - Be concise and cite timestamps or chapter names when relevant
        - You can use general knowledge to interpret or clarify, but don't invent facts

        USER'S QUESTION:
        {question}

        PREVIOUS CONVERSATION:
        {history}

        VIDEO CHAPTERS:
        {chapters}

        TRANSCRIPT:
        {transcript}
        """
    
    def _create_summary(self, session: ChatSession, transcript: str) -> Optional[str]:
        """
        Create compressed summary of conversation when it gets too long
        
        :param session: ChatSession object
        :param transcript: Video transcript text for context
        :return: Summary string or None if failed
        """
        if not self.enabled:
            return None
        
        # Format all messages
        conversation = "\n".join([
            f"{msg['role']}: {msg['content']}"
            for msg in session.history
        ])
        
        # Ask AI to summarize
        prompt = f"""Create a brief summary of this conversation about a video transcript.
            Keep important facts, names, and conclusions. Be concise.

            CONVERSATION:
            {conversation}

            TRANSCRIPT CONTEXT:
            {transcript}

            SUMMARY:"""
        
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            return response.text.strip() if hasattr(response, 'text') else ""
        except Exception:
            return None
