"""Video follow-along tool schemas."""

VIDEO_FOLLOW_TOOLS = [
    {"name": "get_transcript_context", "description": "Get transcript + key points + teaching brief around a DIFFERENT timestamp (not the current one — that's already in your context). Returns everything in one call: transcript window, summary, key points, professor's framing, examples. ONE call is enough — do NOT also call get_section_content or get_section_brief.", "input_schema": {"type": "object", "properties": {"lesson_id": {"type": "number"}, "timestamp": {"type": "number", "description": "Seconds"}}, "required": ["lesson_id", "timestamp"]}},
    {"name": "get_section_content", "description": "Get full content for a DIFFERENT section (not the current one — that's already in your context). Returns transcript + key points + teaching brief + formulas all in one call. ONE call is enough.", "input_schema": {"type": "object", "properties": {"lesson_id": {"type": "number"}, "section_index": {"type": "number"}}, "required": ["lesson_id", "section_index"]}},
    {"name": "resume_video", "description": "Resume video playback. Call when you've answered the student's question. Do NOT ask 'shall we continue?' — just call this.", "input_schema": {"type": "object", "properties": {"message": {"type": "string", "description": "Optional brief note before resuming"}}, "required": []}},
    {"name": "seek_video", "description": "Seek the video to a specific timestamp. Use to point the student to a relevant moment.", "input_schema": {"type": "object", "properties": {"timestamp": {"type": "number"}, "reason": {"type": "string"}}, "required": ["timestamp"]}},
    # capture_video_frame disabled — cross-origin blocks it for YouTube streams
    # {"name": "capture_video_frame", ...},
]


VIDEO_CONTROL_TOOLS = {"resume_video", "seek_video"}

