import type { TranscriptSegment, TranscriptData } from './types';

interface CaptionTrack {
  baseUrl: string;
  name: {
    simpleText: string;
  };
  vssId: string;
  kind?: string;
  isTranslatable?: boolean;
}

interface YouTubeInitialData {
  captions?: {
    playerCaptionsTracklistRenderer?: {
      captionTracks: CaptionTrack[];
    };
  };
}

/**
 * Extract caption tracks from YouTube initial data
 */
function getYouTubeInitialData(): YouTubeInitialData | null {
  const scripts = document.querySelectorAll('script');

  for (const script of scripts) {
    if (script.textContent?.includes('var ytInitialData')) {
      const match = script.textContent.match(/var ytInitialData = ({.*?});/);
      if (match) {
        try {
          return JSON.parse(match[1]) as YouTubeInitialData;
        } catch (e) {
          console.error('Failed to parse YouTube initial data:', e);
        }
      }
    }
  }

  return null;
}

/**
 * Fetch and parse YouTube timedtext (captions)
 */
async function fetchTimedtext(captionUrl: string): Promise<TranscriptSegment[]> {
  try {
    const response = await fetch(captionUrl);
    if (!response.ok) {
      throw new Error(`Failed to fetch captions: ${response.status}`);
    }

    const xml = await response.text();
    return parseTimedtext(xml);
  } catch (error) {
    console.error('Error fetching timedtext:', error);
    return [];
  }
}

/**
 * Parse YouTube XML timedtext format
 * Format: <transcript><entry start="0.5" dur="5.4">Text</entry>...</transcript>
 */
function parseTimedtext(xml: string): TranscriptSegment[] {
  const segments: TranscriptSegment[] = [];

  try {
    const parser = new DOMParser();
    const doc = parser.parseFromString(xml, 'text/xml');

    const entries = doc.querySelectorAll('entry');

    entries.forEach((entry) => {
      const startStr = entry.getAttribute('start');
      const durStr = entry.getAttribute('dur');
      const text = entry.textContent?.trim() || '';

      if (startStr && durStr && text) {
        const startTime = parseFloat(startStr);
        const duration = parseFloat(durStr);
        const endTime = startTime + duration;

        // Clean up HTML entities
        const cleanText = text.replace(/&[^;]+;/g, (entity) => {
          const textarea = document.createElement('textarea');
          textarea.innerHTML = entity;
          return textarea.value;
        });

        segments.push({
          startTime,
          endTime,
          text: cleanText,
        });
      }
    });

    return segments;
  } catch (error) {
    console.error('Error parsing timedtext XML:', error);
    return [];
  }
}

/**
 * Get caption tracks from the current page
 */
function getCaptionTracks(): CaptionTrack[] {
  const initialData = getYouTubeInitialData();

  if (
    initialData?.captions?.playerCaptionsTracklistRenderer?.captionTracks
  ) {
    return initialData.captions.playerCaptionsTracklistRenderer.captionTracks;
  }

  return [];
}

/**
 * Fetch transcript for a YouTube video
 */
export async function fetchYouTubeTranscript(videoId: string): Promise<TranscriptData | null> {
  try {
    const captionTracks = getCaptionTracks();

    if (captionTracks.length === 0) {
      console.log('No caption tracks available for video');
      return null;
    }

    // Prefer English, fallback to first available
    let selectedTrack = captionTracks.find((track) =>
      track.name.simpleText.toLowerCase().includes('english')
    );

    if (!selectedTrack) {
      selectedTrack = captionTracks[0];
    }

    if (!selectedTrack.baseUrl) {
      console.error('No baseUrl in caption track');
      return null;
    }

    // Build the caption URL with proper format
    const captionUrl = new URL(selectedTrack.baseUrl);
    captionUrl.searchParams.set('fmt', 'json3');

    console.log('Fetching captions from:', captionUrl.toString());

    const segments = await fetchTimedtext(captionUrl.toString());

    if (segments.length === 0) {
      console.log('No segments extracted from captions');
      return null;
    }

    const language = selectedTrack.name.simpleText;

    return {
      videoId,
      segments,
      language,
    };
  } catch (error) {
    console.error('Error fetching YouTube transcript:', error);
    return null;
  }
}

/**
 * Cache transcript data in extension storage
 */
export async function cacheTranscript(transcript: TranscriptData): Promise<void> {
  try {
    const cache: Record<string, TranscriptData> = await new Promise((resolve, reject) => {
      chrome.storage.local.get('transcriptCache', (result) => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
        } else {
          resolve((result.transcriptCache as Record<string, TranscriptData>) || {});
        }
      });
    });

    cache[transcript.videoId] = transcript;

    await new Promise<void>((resolve, reject) => {
      chrome.storage.local.set({ transcriptCache: cache }, () => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
        } else {
          resolve();
        }
      });
    });

    console.log(`Cached transcript for video ${transcript.videoId}`);
  } catch (error) {
    console.error('Error caching transcript:', error);
  }
}

/**
 * Get cached transcript
 */
export async function getCachedTranscript(videoId: string): Promise<TranscriptData | null> {
  try {
    const result: Record<string, Record<string, TranscriptData>> = await new Promise(
      (resolve, reject) => {
        chrome.storage.local.get('transcriptCache', (result) => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            resolve(result as Record<string, Record<string, TranscriptData>>);
          }
        });
      }
    );

    const cache = result.transcriptCache || {};
    return cache[videoId] || null;
  } catch (error) {
    console.error('Error retrieving cached transcript:', error);
    return null;
  }
}
