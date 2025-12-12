import type { Message, VideoMetadata, TranscriptData } from './types';

const BACKEND_URL = 'http://localhost:8000';

// Store active video tracking data
interface VideoState {
  metadata: VideoMetadata;
  transcript?: TranscriptData;
  lastUpdateTime: number;
}

const activeVideos = new Map<string, VideoState>();

/**
 * Send playback info to the backend
 */
async function sendToBackend(endpoint: string, data: unknown): Promise<void> {
  try {
    const response = await fetch(`${BACKEND_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      console.error(`Backend request failed: ${response.status} ${response.statusText}`);
    } else {
      console.log(`Successfully sent data to ${endpoint}`);
    }
  } catch (error) {
    console.error(`Error sending data to backend: ${error}`);
  }
}

/**
 * Handle messages from content scripts
 */
chrome.runtime.onMessage.addListener((message: Message, sender, sendResponse) => {
  console.log(`[Background] Received message: ${message.type} from tab ${sender.tab?.id}`);

  (async () => {
    try {
      switch (message.type) {
        case 'VIDEO_DETECTED': {
          const metadata = message.data as VideoMetadata;
          console.log(`Video detected: ${metadata.videoId} - ${metadata.title}`);

          const state: VideoState = {
            metadata,
            lastUpdateTime: Date.now(),
          };
          activeVideos.set(metadata.videoId, state);

          // Send metadata to backend immediately
          await sendToBackend('/api/video/detected', {
            video: metadata,
          });

          sendResponse({ success: true });
          break;
        }

        case 'TRANSCRIPT_FETCHED': {
          const transcript = message.data as TranscriptData;
          const videoId = transcript.videoId;
          console.log(`Transcript received for ${videoId}: ${transcript.segments.length} segments`);

          const state = activeVideos.get(videoId);
          if (state) {
            state.transcript = transcript;

            // Send transcript + metadata to backend
            await sendToBackend('/api/video/detected', {
              video: state.metadata,
              transcript: transcript,
            });
          }

          sendResponse({ success: true });
          break;
        }

        case 'TRANSCRIPT_ERROR': {
          const { videoId, error } = message.data as { videoId: string; error: string };
          console.error(`Transcript error for ${videoId}: ${error}`);

          sendResponse({ success: true });
          break;
        }

        case 'VIDEO_UPDATED': {
          const { videoId, currentTime } = message.data as {
            videoId: string;
            currentTime: number;
          };
          const state = activeVideos.get(videoId);

          if (state) {
            state.metadata.currentTime = currentTime;
            const now = Date.now();
            const timeSinceLastUpdate = now - state.lastUpdateTime;

            // Send playback info to backend periodically (every 5 seconds)
            if (timeSinceLastUpdate > 5000) {
              await sendToBackend('/api/video/playback', {
                video: state.metadata,
                transcript: state.transcript,
              });
              state.lastUpdateTime = now;
            }
          }

          sendResponse({ success: true });
          break;
        }

        case 'VIDEO_STOPPED': {
          const { videoId } = message.data as { videoId: string };
          console.log(`Video stopped: ${videoId}`);

          const state = activeVideos.get(videoId);
          if (state) {
            // Send final state to backend
            await sendToBackend('/api/video/stopped', {
              video: state.metadata,
              transcript: state.transcript,
            });

            activeVideos.delete(videoId);
          }

          sendResponse({ success: true });
          break;
        }

        default:
          console.warn(`Unknown message type: ${message.type}`);
          sendResponse({ error: 'Unknown message type' });
      }
    } catch (error) {
      console.error('Error handling message:', error);
      sendResponse({ error: String(error) });
    }
  })();

  // Return true to indicate we will send response asynchronously
  return true;
});

/**
 * Initialize background worker
 */
chrome.runtime.onInstalled.addListener(() => {
  console.log('[Propaganda Extension] Background service worker installed');
});
