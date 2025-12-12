import type {
  VideoDetectedMessage,
  VideoUpdatedMessage,
  VideoStoppedMessage,
  VideoMetadata,
  TranscriptFetchedMessage,
  TranscriptErrorMessage,
} from './types';
import { fetchYouTubeTranscript, cacheTranscript, getCachedTranscript } from './youtube-transcript';

interface VideoElement {
  element: HTMLVideoElement;
  videoId: string | null;
  isTracking: boolean;
}

const trackedVideos = new Map<HTMLVideoElement, VideoElement>();

/**
 * Extract YouTube video ID from the current page
 */
function getYouTubeVideoId(): string | null {
  // Check URL parameters for v parameter
  const urlParams = new URLSearchParams(window.location.search);
  const videoId = urlParams.get('v');
  if (videoId) return videoId;

  // Fallback: check for video ID in pathname (shorts, etc.)
  const pathMatch = window.location.pathname.match(/\/watch\?v=([^&]+)|\/shorts\/([^?]+)/);
  if (pathMatch) return pathMatch[1] || pathMatch[2];

  return null;
}

/**
 * Extract video title and channel from page
 */
async function getVideoMetadata(): Promise<{
  title: string;
  channel: string;
} | null> {
  // Try to get title from meta tag
  const titleMeta = document.querySelector('meta[name="title"]');
  const title = (titleMeta as HTMLMetaElement)?.content || document.title;

  // Try to get channel from the page
  const channelLink = document.querySelector(
    'a[href*="/channel/"], a[href*="/@"], yt-formatted-string[title]',
  );
  const channel = (channelLink as HTMLElement)?.textContent?.trim() || 'Unknown Channel';

  return { title, channel };
}

/**
 * Send message to background script
 */
async function sendMessageToBackground<T>(message: T): Promise<void> {
  try {
    chrome.runtime.sendMessage(message);
  } catch (error) {
    console.log('Could not send message to background:', error);
  }
}

/**
 * Get video metadata for a given video element
 */
async function getVideoMetadataForElement(video: HTMLVideoElement): Promise<VideoMetadata | null> {
  const videoId = getYouTubeVideoId();

  if (!videoId) {
    console.log('Could not extract video ID');
    return null;
  }

  const metadata = await getVideoMetadata();
  if (!metadata) return null;

  return {
    videoId,
    title: metadata.title,
    channel: metadata.channel,
    currentTime: video.currentTime,
    duration: video.duration,
  };
}

/**
 * Set up event listeners for a video element
 */
function setupVideoTracking(video: HTMLVideoElement): void {
  const videoEntry: VideoElement = {
    element: video,
    videoId: getYouTubeVideoId(),
    isTracking: false,
  };

  trackedVideos.set(video, videoEntry);

  // Initial detection
  video.addEventListener(
    'play',
    async (event) => {
      const video = event.target as HTMLVideoElement;
      const metadata = await getVideoMetadataForElement(video);

      if (metadata) {
        const message: VideoDetectedMessage = {
          type: 'VIDEO_DETECTED',
          data: metadata,
        };
        await sendMessageToBackground(message);
        videoEntry.isTracking = true;

        // Attempt to fetch and send transcript
        try {
          const cached = await getCachedTranscript(metadata.videoId);
          if (cached) {
            console.log('Using cached transcript for', metadata.videoId);
            const transcriptMessage: TranscriptFetchedMessage = {
              type: 'TRANSCRIPT_FETCHED',
              data: cached,
            };
            await sendMessageToBackground(transcriptMessage);
          } else {
            // Try to fetch from YouTube
            const transcript = await fetchYouTubeTranscript(metadata.videoId);
            if (transcript) {
              await cacheTranscript(transcript);
              const transcriptMessage: TranscriptFetchedMessage = {
                type: 'TRANSCRIPT_FETCHED',
                data: transcript,
              };
              await sendMessageToBackground(transcriptMessage);
            }
          }
        } catch (error) {
          console.error('Error handling transcript:', error);
          const errorMessage: TranscriptErrorMessage = {
            type: 'TRANSCRIPT_ERROR',
            data: {
              videoId: metadata.videoId,
              error: String(error),
            },
          };
          await sendMessageToBackground(errorMessage);
        }
      }
    },
    { once: false },
  );

  // Track time updates
  video.addEventListener(
    'timeupdate',
    async (event) => {
      const video = event.target as HTMLVideoElement;
      if (videoEntry.isTracking) {
        const metadata = await getVideoMetadataForElement(video);
        if (metadata) {
          const message: VideoUpdatedMessage = {
            type: 'VIDEO_UPDATED',
            data: {
              videoId: metadata.videoId,
              currentTime: metadata.currentTime,
            },
          };
          await sendMessageToBackground(message);
        }
      }
    },
    { once: false },
  );

  // Track pause
  video.addEventListener(
    'pause',
    async (event) => {
      const video = event.target as HTMLVideoElement;
      if (videoEntry.isTracking) {
        const metadata = await getVideoMetadataForElement(video);
        if (metadata) {
          const message: VideoUpdatedMessage = {
            type: 'VIDEO_UPDATED',
            data: {
              videoId: metadata.videoId,
              currentTime: metadata.currentTime,
            },
          };
          await sendMessageToBackground(message);
        }
      }
    },
    { once: false },
  );

  // Track video end
  video.addEventListener(
    'ended',
    async (event) => {
      const video = event.target as HTMLVideoElement;
      if (videoEntry.isTracking) {
        const metadata = await getVideoMetadataForElement(video);
        if (metadata) {
          const message: VideoStoppedMessage = {
            type: 'VIDEO_STOPPED',
            data: {
              videoId: metadata.videoId,
            },
          };
          await sendMessageToBackground(message);
          videoEntry.isTracking = false;
          trackedVideos.delete(video);
        }
      }
    },
    { once: false },
  );
}

/**
 * Find and track all video elements on the page
 */
function findAndTrackVideos(): void {
  const videos = document.querySelectorAll('video');

  videos.forEach((video) => {
    if (!trackedVideos.has(video)) {
      setupVideoTracking(video);
    }
  });
}

/**
 * Use MutationObserver to watch for new video elements
 */
function setupMutationObserver(): void {
  const observer = new MutationObserver((mutations) => {
    for (const mutation of mutations) {
      if (mutation.type === 'childList') {
        // Check if new video elements were added
        if (mutation.addedNodes.length > 0) {
          findAndTrackVideos();
        }
      } else if (mutation.type === 'attributes') {
        // Watch for changes in video attributes (like src)
        const target = mutation.target as HTMLElement;
        if (target.tagName === 'VIDEO' && !trackedVideos.has(target as HTMLVideoElement)) {
          setupVideoTracking(target as HTMLVideoElement);
        }
      }
    }
  });

  observer.observe(document.documentElement, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: ['src'],
  });
}

/**
 * Initialize content script
 */
function init(): void {
  console.log('[Propaganda Extension] Content script initialized');

  // Find existing videos
  findAndTrackVideos();

  // Watch for new videos
  setupMutationObserver();

  // Try to auto-play detection if video is already playing
  setTimeout(() => {
    const videos = document.querySelectorAll('video');
    videos.forEach(async (video) => {
      if (!video.paused) {
        const metadata = await getVideoMetadataForElement(video as HTMLVideoElement);
        if (metadata) {
          const message: VideoDetectedMessage = {
            type: 'VIDEO_DETECTED',
            data: metadata,
          };
          await sendMessageToBackground(message);
        }
      }
    });
  }, 1000);
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
