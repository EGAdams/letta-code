/**
 * The note box's transcript accumulator.
 *
 * The behaviour moved to `TranscriptBuffer` unchanged when the command channel
 * turned out to need exactly the same buffering (see transcript-buffer.js).
 * This name is kept as the alias its existing callers import.
 */
export { TranscriptBuffer as ReceptionistTranscriptController } from "./transcript-buffer.js";
