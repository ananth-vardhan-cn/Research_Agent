/**
 * Types for message passing between content scripts, background worker, and side panel
 */

export interface VideoMetadata {
  videoId: string;
  title: string;
  channel: string;
  currentTime: number;
  duration: number;
}

export interface TranscriptSegment {
  startTime: number; // in seconds
  endTime: number; // in seconds
  text: string;
}

export interface TranscriptData {
  videoId: string;
  segments: TranscriptSegment[];
  language: string;
}

export type MessageType =
  | 'VIDEO_DETECTED'
  | 'VIDEO_UPDATED'
  | 'VIDEO_STOPPED'
  | 'TRANSCRIPT_FETCHED'
  | 'TRANSCRIPT_ERROR'
  | 'PLAYBACK_INFO';

export interface Message {
  type: MessageType;
  data: unknown;
}

export interface VideoDetectedMessage extends Message {
  type: 'VIDEO_DETECTED';
  data: VideoMetadata;
}

export interface VideoUpdatedMessage extends Message {
  type: 'VIDEO_UPDATED';
  data: {
    videoId: string;
    currentTime: number;
  };
}

export interface VideoStoppedMessage extends Message {
  type: 'VIDEO_STOPPED';
  data: {
    videoId: string;
  };
}

export interface TranscriptFetchedMessage extends Message {
  type: 'TRANSCRIPT_FETCHED';
  data: TranscriptData;
}

export interface TranscriptErrorMessage extends Message {
  type: 'TRANSCRIPT_ERROR';
  data: {
    videoId: string;
    error: string;
  };
}

export interface PlaybackInfoMessage extends Message {
  type: 'PLAYBACK_INFO';
  data: VideoMetadata & {
    transcript?: TranscriptData;
  };
}
