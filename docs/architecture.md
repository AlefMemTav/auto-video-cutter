# Architecture Overview

This document describes the architecture, design decisions, and execution flow of **auto-video-cutter**.

The goal of this system is to automatically generate video cuts (shorts or long-form clips) from long videos using a **deterministic, CPU-only, high-performance pipeline**.

---

## 1. Architectural Principles

The system is designed around the following principles:

- **Automation first**: zero manual editing
- **Determinism over hype**: predictable outputs
- **Performance-aware**: FFmpeg over Python frame processing
- **Cost-free**: CPU-only, local execution
- **Extensibility**: features are plug-in, not hard-wired

---

## 2. High-Level Pipeline

The system operates as a batch processing pipeline.  
Each input video is processed independently as a **job**.

```mermaid
%%{init: {"theme":"base", "themeVariables": {"background":"#ffffff"}}}%%
flowchart TD
    A[Input Video<br/>MP4/MKV] --> B[Ingest<br/>job_id + storage]
    B --> C[Extract Audio<br/>ffmpeg]
    C --> D[Transcription<br/>faster-whisper]
    D --> E[Segmenter<br/>heurística]
    E --> F[Subtitle Generator<br/>.ass]
    F --> G[Renderer<br/>ffmpeg filter_complex]
    G --> H[Outputs<br/>Shorts / Cuts]
```

Key stages:
1. Ingest video and create isolated job workspace
2. Extract audio optimized for speech recognition
3. Transcribe audio using Whisper
4. Segment transcript using deterministic heuristics
5. Generate styled subtitles (.ass)
6. Render final clips using FFmpeg

---

## 3. Job-Based Execution Model

Each video is processed as a single job in a queue.

- Jobs are **stateless**
- Workers can scale horizontally
- Failures affect only one job
- No shared mutable state

```mermaid
%%{init: {"theme":"base", "themeVariables": {"background":"#ffffff"}}}%%
sequenceDiagram
    participant CLI as CLI / API
    participant RQ as Redis Queue
    participant W as Worker
    participant FS as Filesystem

    CLI->>RQ: enqueue(job_id)
    RQ->>W: dispatch job
    W->>FS: save input.mp4
    W->>FS: extract audio.wav
    W->>FS: generate transcript.json
    W->>FS: generate segments.json
    loop for each segment
        W->>FS: generate subtitles.ass
        W->>FS: render short.mp4
    end
    W->>RQ: job finished
```

This model allows safe retries and parallel execution.

---

## 4. Storage Layout

Each job has its own isolated directory:

```
storage/jobs/{job_id}/
├── input.mp4
├── audio.wav
├── transcript.json
├── segments.json
├── subtitles/
│ └── segment_01.ass
└── outputs/
└── segment_01.mp4
```

This guarantees:
- traceability
- reproducibility
- easy debugging

---

## 5. Transcription Layer

Audio is extracted and normalized before transcription.

- Mono
- 16 kHz sample rate
- Optimized for Whisper accuracy

The transcription output is a structured JSON containing:
- text
- start timestamp
- end timestamp

This data becomes the **single source of truth** for segmentation.

---

## 6. Segmentation Strategy

Segmentation is heuristic-based by design.

Goals:
- avoid heavy ML models
- keep execution fast and deterministic
- ensure semantic coherence

Rules:
- group consecutive phrases
- close segments only on `. ? !`
- enforce min/max duration per profile
- discard low-content segments

```mermaid
%%{init: {"theme":"base", "themeVariables": {"background":"#ffffff"}}}%%
flowchart LR
    A[Whisper JSON<br/>phrases + timestamps] --> B[Group phrases]
    B --> C{Duration < min?}
    C -- Yes --> B
    C -- No --> D{Ends with . ? !}
    D -- No --> B
    D -- Yes --> E{Duration > max?}
    E -- Yes --> F[Close segment]
    E -- No --> B
    F --> G[Save segment]
```

LLM-based segmentation is intentionally disabled by default and treated as an optional extension.

---

## 7. Output Profiles

The renderer supports multiple output profiles.

Examples:
- Shorts (9:16, 30–60s, blur background)
- Medium clips (16:9, 3–8 min, no blur)

Profiles control:
- segment duration
- aspect ratio
- background strategy
- subtitle style

```mermaid
%%{init: {"theme":"base", "themeVariables": {"background":"#ffffff"}}}%%
flowchart TD

    A[Segment] --> B{Profile}
    B -->|Short| C[9:16<br/>Blur ON<br/>30-60s]
    B -->|Medium| D[16:9<br/>Blur OFF<br/>3-8min]

    C --> E[Renderer]
    D --> E
```

---

## 8. Rendering Engine

Rendering is fully handled by **FFmpeg** using `filter_complex`.

Rendering steps:
1. Split video into background and foreground
2. Scale and blur background
3. Scale foreground to fit
4. Overlay foreground on background
5. Burn-in subtitles (.ass)

```mermaid
%%{init: {"theme":"base", "themeVariables": {"background":"#ffffff"}}}%%
flowchart TD
    A[Input Video Segment] --> B[Split Video]
    B --> C[Background Path]
    B --> D[Foreground Path]

    C --> C1[Scale to 9:16]
    C1 --> C2[Crop]
    C2 --> C3[Box Blur]

    D --> D1[Scale to Fit]

    C3 --> E[Overlay]
    D1 --> E

    E --> F[Burn-in Subtitles<br/>ASS]
    F --> G[Final Output MP4]
```

This approach avoids:
- face tracking
- destructive crops
- frame-by-frame Python processing

---

## 9. Subtitle System (.ASS)

Subtitles are generated as `.ass` files to allow:

- font control
- outline and shadow
- precise positioning
- high-performance burn-in

This is significantly faster and more reliable than Python-based video rendering libraries.

---

## 10. Asynchronous Processing

The system uses:
- Redis
- RQ (Redis Queue)

Characteristics:
- simple configuration
- predictable execution
- easy debugging
- minimal operational overhead

---

## 11. Feature Flags and Extensions

Optional features are implemented via feature flags.

Examples:
- LLM-based segment selection
- Multi-output rendering
- Auto-upload to platforms

```mermaid
%%{init: {"theme":"base", "themeVariables": {"background":"#ffffff"}}}%%
flowchart TD
    A[Transcript] --> B{ENABLE_LLM?}
    B -- false --> C[Heuristic Segmenter]
    B -- true --> D[LLM Selector]
    C --> E[Segments]
    D --> E

```

This prevents overengineering while keeping the system extensible.

---

## 12. What This Architecture Explicitly Avoids

By design, the system does **not** include:

- Web UI
- Visual editor
- GPU dependency
- Emotion detection
- Face tracking
- Animated captions

These decisions favor reliability and maintainability.

---

## 13. Summary

This architecture prioritizes:

- simplicity
- performance
- deterministic behavior
- engineering trade-offs made explicit

It is designed to scale **in complexity only when justified**, not by default.

---
