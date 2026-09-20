export interface VoiceUploadSuccess {
  ok: true;
  raw_transcript: string;
  cleaned_text: string;
}
export declare function recordingFilename(
  mimeType: string,
  preferred?: string,
): string;
export declare function parseVoiceUploadResponse(
  value: unknown,
): VoiceUploadSuccess;
