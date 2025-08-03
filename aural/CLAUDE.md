# Workflow

## Data Model

### Core Principle: Audio-Centric Architecture

**Audio files are the foundation** - without audio, there is no release. Everything else enriches the audio with metadata.

### Data Hierarchy

```
Audio File (required - from Soundgasm, Whyp.it, HotAudio)
├── Enrichment Data (from Reddit/Patreon posts)
│   ├── Title
│   ├── Date
│   ├── Primary Performer
│   └── Additional metadata
├── Script (optional - from scriptbin.works, etc.)
└── Artwork (optional)

Release (collection of related audio variants)
├── Audio Variant 1 (e.g., M4F version)
├── Audio Variant 2 (e.g., F4M version)
├── Audio Variant 3 (e.g., with SFX)
└── Audio Variant 4 (e.g., without SFX)
```

### Platform Roles

- **Audio Platforms** (Soundgasm, Whyp.it, HotAudio): Source of audio files (required)
- **Post Platforms** (Reddit, Patreon): Source of enrichment metadata
- **GWASI**: Index into Reddit posts (not primary source)
- **Script Platforms** (scriptbin.works): Optional script content
- **Aggregation System**: Links related audios into releases

### Recommended Directory Structure

```
data/
├── audio/                    # Primary data - audio files
│   ├── soundgasm/           # Audio files from Soundgasm
│   ├── whypit/              # Audio files from Whyp.it
│   └── hotaudio/            # Audio files from HotAudio
├── enrichment/              # Metadata from posts
│   ├── reddit/              # Reddit post metadata
│   │   └── gwasi/           # GWASI index of Reddit (2.7GB existing)
│   └── patreon/             # Patreon post metadata
├── scripts/                 # Optional script files
│   └── scriptbin/           # Scripts from scriptbin.works
├── artwork/                 # Optional artwork files
└── releases/                # Aggregated releases
    └── release_db.json      # Links audios into releases
```

## Overview

Releases consist of:

- At least one audio file.
- Possible alternative audios such as some audios are targeted separately for men and women.
- Possibly a script. Some audio files are so called private fills so the script has been provided privately to the voice actors.
- Possible artwork.

Same script can be used for multiple releases i.e. multiple voice actors can perform the same script and provide multiple alternative audios.

Same audio can be released on multiple platforms. For example an audio can have an early release on Patreon and then public release on Reddit.

Posts can be found either at:

- GWASI and Reddit
- Reddit
- Patreon
- Pornhub

Audio files can be found at:

- Soundgasm
- Whyp.it
- HotAudio
- Patreon
- Pornhub

Pornhub is typically not listed in Reddit posts.

Releases are typically done by a single voice actor but sometimes there are multiple. Reddit always has just single poster so the other voice actors need to be extracted from the text. If the release is on HotAudio, there can be structured data for other voice actors.

Releases should be stored to Stashapp which is primarily meant for organizing videos and performers but we can wrap the audios as video files with static images.

## Examples:

### Threesome At The Milk Maid Cafe!

Voice actors: SnakeySmut, alekirser
Scribe: Enno_Zalenno2

Script: Private fill

Reddit: https://www.reddit.com/r/gonewildaudio/comments/1mf0zav/ff4m_threesome_at_the_milk_maid_cafe_script_fill/

Audios:

- https://soundgasm.net/u/SnakeySmut/Threesome-At-The-Milk-Maid-Cafe
- https://whyp.it/tracks/299338/threesome-at-the-milk-maid-cafe?token=xOYMf
- https://www.pornhub.com/view_video.php?viewkey=688a9b1ce032c

### Shy Ghost Girl Possesses You To Feel Pleasure Again

Voice actors: Lurkydip
Scribe: TheWritingJedi

Script:

- Reddit: https://www.reddit.com/r/gonewildaudio/comments/1me43oy/f4m_shy_ghost_girl_possesses_you_to_feel_pleasure/
- scriptbin.works: https://scriptbin.works/u/TheWritingJedi/f4m-shy-ghost-girl-possesses-you-to-feel-pleasure

Reddit: https://www.reddit.com/r/gonewildaudio/comments/1mf1onp/f4m_shy_ghost_girl_possesses_you_to_feel_pleasure/

Audios:

- https://hotaudio.net/u/Lurkydip/Shy-Ghost-Girl-Possesses-You-To-Feel-Pleasure-Again
- https://soundgasm.net/u/LurkyDip/Shy-Ghost-Girl-Possesses-You-To-Feel-Pleasure-Again
- https://whyp.it/tracks/299350/shy-ghost-girl-possesses-you-to-feel-pleasure-again
