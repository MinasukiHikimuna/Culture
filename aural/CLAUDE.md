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

# Technical Implementation Workflow

## Phase 1: Discovery & Indexing

### Data Sources Priority
1. **GWASI API** (`gwasi_extractor.py`)
   - Primary index for Reddit content discovery
   - Provides structured metadata and Reddit post IDs
   - Use for bulk discovery and historical data analysis

2. **Reddit API** (PRAW integration)
   - Direct access to post content and comments
   - Real-time monitoring of new posts
   - Required for content analysis and link extraction

3. **Patreon Integration**
   - Premium/early access content discovery
   - Performer-specific release monitoring
   - Requires authentication and subscription management

### Implementation Tasks
- [ ] Enhance GWASI extractor with post content analysis
- [ ] Implement Reddit PRAW integration for content parsing
- [ ] Build Patreon API integration for premium content
- [ ] Create unified post discovery queue

## Phase 2: Content Analysis Engine

### Post Parsing Requirements
```python
class PostAnalyzer:
    def extract_performers(self, post_content: str) -> List[str]:
        # Extract voice actors from post text and tags
        pass
    
    def extract_audio_links(self, post_content: str) -> List[AudioLink]:
        # Parse Soundgasm, Whyp.it, HotAudio URLs
        pass
    
    def extract_script_info(self, post_content: str) -> Optional[ScriptInfo]:
        # Find script sources and scriptbin.works links
        pass
    
    def categorize_release(self, post: Post) -> ReleaseCategory:
        # Determine release type (script fill, improvisation, etc.)
        pass
```

### Platform-Specific Extractors
- **Soundgasm**: Parse user profiles and audio metadata
- **Whyp.it**: Handle token-based URLs and track information
- **HotAudio**: Extract structured performer data
- **Scriptbin.works**: Parse script content and metadata

### Implementation Tasks
- [ ] Build regex patterns for audio URL extraction
- [ ] Implement platform-specific metadata extractors
- [ ] Create performer name normalization system
- [ ] Build tag standardization engine

## Phase 3: Download Management

### Download Orchestration
```python
class DownloadManager:
    def plan_downloads(self, releases: List[Release]) -> DownloadPlan:
        # Prioritize downloads based on storage and preferences
        pass
    
    def download_audio(self, audio_link: AudioLink) -> AudioFile:
        # Platform-specific audio download with retry logic
        pass
    
    def download_script(self, script_link: ScriptLink) -> ScriptFile:
        # Script content extraction and storage
        pass
    
    def download_artwork(self, post: Post) -> List[ArtworkFile]:
        # Extract and download associated images
        pass
```

### Platform Download Strategies
- **Soundgasm**: Direct MP3/M4A download with metadata preservation
- **Whyp.it**: Token-based download with session management
- **HotAudio**: Account-based download with authentication
- **Patreon**: Subscriber-only content with authentication

### Implementation Tasks
- [ ] Build platform-specific download adapters
- [ ] Implement retry logic and error handling
- [ ] Create storage deduplication system
- [ ] Build download progress tracking

## Phase 4: Metadata Enrichment

### Release Aggregation
```python
class ReleaseAggregator:
    def group_audio_variants(self, audios: List[AudioFile]) -> List[Release]:
        # Group related audios (M4F/F4M, SFX variants, etc.)
        pass
    
    def link_scripts_to_releases(self, releases: List[Release], scripts: List[Script]) -> None:
        # Associate scripts with their audio performances
        pass
    
    def build_performer_profiles(self, releases: List[Release]) -> List[Performer]:
        # Create comprehensive performer database
        pass
```

### Metadata Standardization
- **Tags**: Normalize content tags across platforms
- **Performers**: Build unified performer database with aliases
- **Durations**: Extract and standardize audio duration metadata
- **Quality**: Assess audio quality and format information

### Implementation Tasks
- [ ] Build release grouping algorithms
- [ ] Create performer identity resolution system
- [ ] Implement tag taxonomy and normalization
- [ ] Build quality assessment tools

## Phase 5: Stashapp Integration

### Media Format Conversion
```python
class StashappAdapter:
    def convert_audio_to_video(self, audio: AudioFile, artwork: Optional[ArtworkFile]) -> VideoFile:
        # Convert audio to video format with static image
        pass
    
    def generate_stashapp_metadata(self, release: Release) -> StashappScene:
        # Map release metadata to Stashapp schema
        pass
    
    def import_to_stashapp(self, scenes: List[StashappScene]) -> None:
        # Import content via Stashapp API
        pass
```

### Stashapp Schema Mapping
- **Scenes**: Audio releases as video scenes
- **Performers**: Voice actors as performers
- **Tags**: Content tags and categories
- **Studios**: Production groups or series

### Implementation Tasks
- [ ] Build FFmpeg-based audio-to-video conversion
- [ ] Create Stashapp API integration
- [ ] Implement metadata schema mapping
- [ ] Build batch import functionality

## Quality Assurance & Monitoring

### Data Validation
- Verify audio file integrity and playability
- Validate metadata completeness and accuracy
- Check for duplicate content across sources
- Monitor download success rates and failures

### Error Handling
- Implement comprehensive logging and error tracking
- Build retry mechanisms for failed downloads
- Create manual review queues for problematic content
- Monitor platform API changes and adapt accordingly

### Implementation Tasks
- [ ] Build comprehensive test suite
- [ ] Implement data validation pipelines
- [ ] Create monitoring and alerting system
- [ ] Build manual review and correction tools
