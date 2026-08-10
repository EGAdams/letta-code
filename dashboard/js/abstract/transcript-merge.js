/**
 * mergeFinalChunk — append a newly-finalized SpeechRecognition chunk onto
 * already-committed transcript text, trimming any word-level overlap the
 * chunk repeats from the tail of `committed`.
 *
 * Why this exists: BrowserSpeechRecognitionListener restarts the native
 * recognizer on every silence-triggered `onend` to keep "continuous"
 * listening actually continuous (see that file). On Android Chrome's
 * cloud-backed engine, that restart frequently re-flushes and re-transcribes
 * the tail of the previous utterance as part of the next "final" result —
 * sometimes verbatim, sometimes re-worded. Naively concatenating every final
 * chunk (the old behavior) let that repeated/garbled tail show up as doubled
 * or scrambled words in the transcript, compounding on every restart during
 * a long "Start Listening" session.
 */
export function mergeFinalChunk(committed, chunk) {
  const committedWords = committed ? committed.trim().split(/\s+/) : [];
  const chunkWords = chunk ? chunk.trim().split(/\s+/).filter(Boolean) : [];
  if (!chunkWords.length) return committed;
  if (!committedWords.length) return chunkWords.join(" ");

  const maxOverlap = Math.min(committedWords.length, chunkWords.length, 8);
  for (let n = maxOverlap; n > 0; n--) {
    const tail = committedWords.slice(-n).join(" ").toLowerCase();
    const head = chunkWords.slice(0, n).join(" ").toLowerCase();
    if (tail === head) {
      const remainder = chunkWords.slice(n);
      return remainder.length
        ? `${committed} ${remainder.join(" ")}`
        : committed;
    }
  }
  return `${committed} ${chunkWords.join(" ")}`;
}
