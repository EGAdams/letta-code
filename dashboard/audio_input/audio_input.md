## Update the Agent Input Page and Add Voice Input

In each specific Agent menu, rename the **“Tests”** section to **“Input Options.”**

For now, keep the existing text and layout on that page the same, including:

```text
Send a test message to {Agent_Name}
```

and the existing related divs.

## Add Voice Input Controls

Copy the existing voice system web page interface that was previously found and integrate a copy of it into this system so we can use voice input here.

Add one new button to the dashboard:

```text
Start
```

Button behavior:

1. The button should match the current **Send** button style.
2. The default button color should be **green**.
3. The default text should be **Start** in **black**.
4. When clicked:

   * Change the button text to **Stop**.
   * Change the button color to **red**.
   * Change the text color to **white**.
   * Start recording audio.
5. When clicked again:

   * Stop recording audio.
   * Convert the audio to text.
   * Send the converted text through a cheaper, faster LLM for cleanup before passing it to the main Agent/LLM.

## Recording Indicator

While recording, show a recording indicator to the right of the button.

The indicator should look like a white LED-style square containing a blinking red circle.

Next to or inside the indicator, cycle the recording text like this:

```text
Recording
Recording.
Recording..
Recording...
```

Repeat this cycle while audio is being recorded.

## Voice Transcript Cleanup

After speech-to-text conversion, send the transcript to a cheaper, faster LLM before it reaches the main Agent.

The cleanup LLM should:

1. Format the transcript so it makes sense.
2. Correct obvious speech-to-text mistakes.
3. Use company/project context to fix names and terms.
4. Prevent bad or confusing transcript data from being sent to the main LLM.

Example:

If the speech-to-text system produces:

```text
Tell Friday about this.
```

but there is no Letta Agent named **Friday**, and there is a known Letta Agent named **Frita**, the cleanup LLM should correct it to:

```text
Tell Frita about this.
```

The cleanup model should make these corrections only when the intended meaning is reasonably clear from known company context.
