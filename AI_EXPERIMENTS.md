# AI experiments

A working journal of the experiments with the AI provider: what was tried, what
worked and what did not.

## Gemini trial script

Before the Gemini API is used in the application, it was tried in a separate
script, `backend/scripts/try_gemini.py`. Run it from the `backend/` folder:

```bash
python -m scripts.try_gemini uploads/4/audio.mp3
```

### Setup

| Item         | Value                                                      |
|--------------|------------------------------------------------------------|
| SDK          | `google-genai` 2.29.0 (Python 3.14.5)                      |
| Model        | `gemini-3.8-flash` (`GEMINI_MODEL`), for both calls        |
| Test file    | MP3, mono, 16 kHz, 64 kbit/s, 1.1 MB, about 2.5 minutes    |
| Test content | One speaker, English, a tutorial (not a real meeting)      |

### How it works

1. The MP3 is uploaded with the Files API (`client.files.upload`).
2. First call: the audio and a text instruction go to `generate_content`, and
   the answer is the transcript as plain text.
3. Second call: the transcript and an instruction go to `generate_content` with
   `response_mime_type="application/json"` and a Pydantic class as
   `response_schema`. `response.parsed` is then an object of that class
   (summary, key topics, action items with assignee and description).
4. The uploaded file is deleted from Google's storage right after the first call.

### Results of one run

| Step          | Time  | Tokens (in / out) |
|---------------|-------|-------------------|
| Upload        | 3.1 s | -                 |
| Transcription | 7.9 s | 3691 / 708        |
| Analysis      | 9.0 s | 786 / 123         |

### What worked

- The upload, and the audio file as input to `gemini-3.8-flash`. The file was
  ready at once; the wait for the `PROCESSING` state was never needed.
- The transcript was complete and read correctly.
- Structured output: the answer fitted the Pydantic schema on the first try and
  `response.parsed` returned the object, with no manual JSON parsing.
- The summary and the four key topics matched the recording.
- The action items list was empty, which is correct for this recording.
- Errors: an unknown model name gives `errors.APIError` with code 404 and a
  readable message, which the script prints without a traceback.

### Two more runs, on meeting recordings

Both are English recordings with several speakers. The audio was extracted
from the MP4 with the application's own `extract_audio`.

| Recording             | Length | MP3     | Transcription             | Analysis                |
|-----------------------|--------|---------|---------------------------|-------------------------|
| Weekly school meeting | 1:38   | 0.75 MB | 5.7 s, 2536 / 503 tokens  | 11.2 s, 581 / 215       |
| Sprint meeting        | 9:11   | 4.2 MB  | 14.1 s, 13834 / 1898      | 5.0 s, 1976 / 540       |

What worked:

- Both runs finished without errors, and the nine-minute recording was
  transcribed in 14 seconds.
- The summaries and key topics matched the transcripts.
- Action items were found: 4 in the short recording and 10 in the long one.
  Items that nobody took on ("let's try a pancake breakfast next week") were
  correctly left without an assignee.

What did not work:

- Speaker labels are not reliable. The short recording got `Speaker 1` to
  `Speaker 6`; the long one got no labels at all, only one line per turn,
  although the prompt was the same.
- Without labels the model cannot tell who said "I'll draft the release notes",
  so 9 of the 10 action items of the long recording have no assignee.
- In the short recording the assignee is a label, not a name (`Speaker 5`),
  because the people never say their names. Names that are only visible on the
  screen are lost, since only the audio is sent.
- The transcripts were not compared with the recordings word by word.

### Second version of the prompts

Two changes, then the same two recordings again:

- Transcription: every line must begin with a speaker label, and the same
  voice keeps the same label in the whole recording.
- Analysis: the assignee is the person who takes the task on, given by real
  name. When the name is never said, the assignee is null; a label such as
  `Speaker 5` is never used as the assignee.

The rule for the assignee was chosen on purpose: the field holds either a name
that was said in the meeting or nothing, so it never holds a label that only
makes sense next to the transcript.

| Recording             | Transcription                | Analysis             | Action items | With a name |
|-----------------------|------------------------------|----------------------|--------------|-------------|
| Weekly school meeting | 13.6 s, 2569 / 502 tokens    | 12.5 s, 671 / 205    | 4            | 0           |
| Sprint meeting        | 56.0 s, 13867 / 2216 tokens  | 13.3 s, 2385 / 253   | 6            | 1           |

- Speaker labels are now consistent: the long recording has `Speaker 1` to
  `Speaker 8` on every line. Whether each label is the right voice was not
  checked against the video.
- No label ends up as an assignee any more. The only assignee is `George`,
  the one name that is said in the recordings.
- Most action items therefore have no assignee on these two recordings. That
  is correct by the rule above, but it means the "person and task" case is
  proven only for one name; a recording where people use each other's names
  is still needed.
- The output changes from run to run: the long recording gave 10 action items
  the first time and 6 the second time (similar items were merged, and two
  from the first run, the post-release review meeting and the final checks,
  are missing).
- The stricter transcription prompt was slower on the long recording (56 s
  instead of 14 s). The total token count is about 7,600 higher than input
  plus output, which points to the model's thinking tokens.

### What was not tested yet

- Speech in Serbian.
- A long recording (30 minutes or more) and the quota limits.

## AI service and the Interactions API

The code of the trial script was moved to `backend/app/services/ai.py`. It has
two functions, `transcribe_audio(audio_path)` and
`analyze_transcript(transcript)`, and one exception, `AIServiceError`, whose
message is safe to show to the user. The script `scripts/try_gemini.py` now
only calls these two functions and prints the result.

### From generateContent to the Interactions API

The first version of the service used `client.models.generate_content`, like
the trial script. Google's documentation says that the Interactions API
(`client.interactions.create`) is the default interface since June 2026 and
should be used for new projects, while `generateContent` is "legacy" but still
fully supported, with no shutdown date. This is a new project, so the service
was moved to the Interactions API before the first commit. No new dependency
was needed: it is part of the same `google-genai` 2.29.0 package.

| Topic             | generateContent                           | Interactions API                                              |
|-------------------|-------------------------------------------|---------------------------------------------------------------|
| Call              | `client.models.generate_content`          | `client.interactions.create`                                  |
| Input             | `contents=[prompt, file]`                 | `input=[{"type": "text", ...}, {"type": "audio", "uri": ...}]` |
| Answer            | `response.text`                           | `interaction.output_text`, plus `interaction.status`          |
| Structured output | `response_schema=Model`, `response.parsed` | `response_format` with a JSON schema, then `Model.model_validate_json` |
| Errors            | `google.genai.errors.APIError` (`.code`)  | a separate `APIError` family (`.status_code`)                 |
| Stored by Google  | no                                        | yes by default, unless `store=False`                          |

The audio still goes through the Files API first and is deleted right after
the call; only the way the request points to it changed.
