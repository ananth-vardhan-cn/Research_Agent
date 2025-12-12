# Video Detection Implementation Notes

## Overview

This implementation adds video detection and transcript acquisition capabilities to the Propaganda Extension.

## Components

### Frontend Extension

#### 1. **types.ts**
TypeScript interfaces for message passing between extension components:
- `VideoMetadata` - contains videoId, title, channel, currentTime, duration
- `TranscriptSegment` - individual caption with startTime, endTime, text
- `TranscriptData` - complete transcript with segments and language
- Message types: `VIDEO_DETECTED`, `VIDEO_UPDATED`, `VIDEO_STOPPED`, `TRANSCRIPT_FETCHED`, `TRANSCRIPT_ERROR`, `PLAYBACK_INFO`

#### 2. **content.ts**
Content script injected into YouTube pages that:
- Uses MutationObserver to detect new video elements
- Sets up event listeners for `play`, `pause`, `timeupdate`, `ended` events
- Extracts YouTube video metadata (videoId, title, channel) from the page
- Fetches transcripts using the youtube-transcript module
- Caches transcripts in extension storage
- Sends structured messages to the background worker via `chrome.runtime.sendMessage`

#### 3. **youtube-transcript.ts**
YouTube transcript extraction utility that:
- Parses YouTube's initial data from the page to find caption tracks
- Fetches YouTube timedtext (XML format) from caption URLs
- Parses XML to extract timestamped transcript segments
- Provides caching functions to store transcripts in extension storage by videoId
- Supports HTML entity decoding in transcript text

#### 4. **background.ts**
Service worker that:
- Listens for messages from content scripts
- Maintains state of active video playbacks
- Sends video metadata to backend endpoints on `VIDEO_DETECTED`
- Receives and forwards transcript data via `TRANSCRIPT_FETCHED` messages
- Throttles playback updates (sends every 5 seconds)
- Sends final state on `VIDEO_STOPPED`
- Communicates with backend via fetch API

#### 5. **manifest.json**
Updated Manifest V3 configuration:
- Content script injected on all YouTube domains: `*://www.youtube.com/*`
- Permissions: `storage` (for caching), `tabs` (for tab queries)
- Host permissions for backend and YouTube
- Background service worker configured as ES module

### Backend API

#### 1. **app/main.py**
FastAPI endpoints added:

- `POST /api/video/detected` - Receives video metadata and optional transcript
  - Stores in Redis with key `video:{videoId}`
  - Stores transcript with key `transcript:{videoId}` if provided
  - Logs with structured logging

- `POST /api/video/playback` - Receives periodic playback updates
  - Stores current time and duration in Redis with key `playback:{videoId}`
  - Logs playback info

- `POST /api/video/stopped` - Receives final state when video ends
  - Records completion status in Redis with key `video_session:{videoId}`
  - Logs completion

## Data Flow

1. **Video Detection**
   ```
   YouTube Page (video element)
   → Content Script detects via MutationObserver
   → Extracts video metadata
   → Sends VIDEO_DETECTED message
   → Background worker receives message
   → Background worker sends /api/video/detected to backend
   ```

2. **Transcript Acquisition**
   ```
   YouTube Page (DOM)
   → Content Script fetches YouTube initial data
   → Extracts caption track URLs
   → Fetches and parses timedtext XML
   → Caches transcript in extension storage
   → Sends TRANSCRIPT_FETCHED message
   → Background worker receives and forwards to backend
   ```

3. **Playback Tracking**
   ```
   Video element timeupdate event
   → Content Script sends VIDEO_UPDATED message
   → Background worker throttles and sends to /api/video/playback
   ```

4. **Completion**
   ```
   Video element ended event
   → Content Script sends VIDEO_STOPPED message
   → Background worker sends /api/video/stopped
   → Backend records final session state
   ```

## Features

✅ **Video Detection**
- MutationObserver watches for new video elements on YouTube
- Extracts videoId, title, channel from page
- Detects on play, tracks time, detects on pause/stop

✅ **Transcript Acquisition**
- Fetches YouTube timedtext from caption tracks
- Parses XML format to extract timestamped segments
- Caches per videoId in extension storage
- Supports fallback to English captions
- Handles HTML entity decoding

✅ **Message Passing**
- Structured TypeScript types for all messages
- Async message handler in background worker
- Proper error handling and logging

✅ **Backend Integration**
- REST API endpoints for video events
- Redis storage for metadata and transcripts
- Structured logging with contextual information
- Error handling and graceful degradation

## Testing the Implementation

### 1. Build the Extension
```bash
cd propaganda_extension/extension
npm install
npm run build
```

### 2. Load in Chrome
- Open `chrome://extensions`
- Enable "Developer mode"
- Click "Load unpacked"
- Select `propaganda_extension/extension/dist`

### 3. Run the Backend
```bash
cd propaganda_extension/backend
uv sync
uv run fastapi dev app/main.py
```

Backend will be available at `http://localhost:8000`

### 4. Test on YouTube
- Navigate to any YouTube video
- Open Chrome DevTools → Console
- You should see logs like:
  - `[Propaganda Extension] Content script initialized`
  - `Video detected: [videoId] - [title]`
  - Log messages from background worker

### 5. Verify Backend Receives Data
- Check `http://localhost:8000/health` - should show redis status
- Video data is stored in Redis keys: `video:{videoId}`, `transcript:{videoId}`

## Architecture Decisions

1. **Content Script for Transcript Fetching**
   - The content script runs on YouTube and has direct access to the DOM
   - This allows fetching transcripts without additional permissions
   - Transcripts are cached to avoid repeated fetches

2. **Message-Based Communication**
   - Clean separation between content script and background worker
   - Supports future extensions (e.g., side panel UI)
   - Type-safe message passing with TypeScript

3. **Throttled Backend Updates**
   - Playback updates sent every 5 seconds, not on every timeupdate event
   - Reduces server load and network traffic
   - Background worker tracks last update time

4. **Graceful Degradation**
   - If transcript fetch fails, video metadata still sent to backend
   - If backend is unreachable, extension continues to function
   - Error messages logged for debugging

## Future Enhancements

- [ ] Side panel UI for displaying transcript alongside video
- [ ] WebSocket support for real-time transcript streaming
- [ ] Support for other video hosts (not just YouTube)
- [ ] Transcript search and highlighting
- [ ] Analytics on transcript completion
