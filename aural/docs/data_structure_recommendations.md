# Data Structure Recommendations for Aural

## Executive Summary

After analyzing the HotAudio LUST Project's complex interactive audio structure and comparing it with our current `analysis_results` format, I recommend a fundamental restructuring of our data model. The current model incorrectly assumes one-to-one relationships between releases, performers, and scripts, when the reality is many-to-many relationships with complex hierarchies.

## Current Issues

### 1. Incorrect Relationship Assumptions
- **Current**: One set of performers per release
- **Reality**: Each audio can have different performers
- **Example**: LUST Project has 16 different voice actors across 30+ audio segments

### 2. Script Attribution Problems
- **Current**: One script per release
- **Reality**: Each audio segment can have its own writer
- **Example**: LUST Project has 12 different script writers

### 3. Flat Structure Limitations
- **Current**: Simple list of audio versions (M4F, F4M, SFX variants)
- **Reality**: Complex branching narratives, series, and interactive stories
- **Example**: LUST Project has 10 levels of branching depth

### 4. Lost Metadata
- **Current**: Aggregate metadata at release level
- **Reality**: Rich metadata exists per audio (duration, tags, credits)
- **Impact**: Loss of attribution and searchability

## Recommended Data Model

### Core Principles

1. **Audio-Centric Architecture**: Each audio is a first-class entity
2. **Flexible Relationships**: Support for complex hierarchies and relationships
3. **Complete Attribution**: Preserve all contributor information
4. **Platform Agnostic**: Support multiple sources for the same content
5. **Extensible**: Easy to add new metadata types

### Proposed Structure

```json
{
  "release": {
    "id": "unique_release_identifier",
    "title": "Release Title",
    "type": "single|series|interactive|compilation",
    "created_at": "ISO-8601 timestamp",
    "updated_at": "ISO-8601 timestamp",
    "version": "2.0"
  },
  
  "audios": [
    {
      "audio_id": "unique_audio_identifier",
      "title": "Individual Audio Title",
      "description": "Detailed description",
      "duration": "duration in minutes or seconds",
      "published_date": "ISO-8601 date",
      
      "performers": [
        {
          "name": "performer_username",
          "role": "voice|editor|producer|mixer",
          "primary": true|false,
          "platform_profile": "URL to performer profile"
        }
      ],
      
      "script": {
        "url": "URL to script",
        "author": "script_writer_username",
        "fill_type": "public|private|commission|original",
        "platform": "scriptbin|reddit|pastebin"
      },
      
      "files": [
        {
          "platform": "Soundgasm|Whyp.it|HotAudio|Patreon",
          "url": "original_audio_url",
          "filename": "local_filename.ext",
          "metadata_file": "local_metadata.json",
          "checksum": "sha256_hash",
          "size_bytes": 12345678,
          "format": "m4a|mp3|wav",
          "bitrate": "128k",
          "downloaded_at": "ISO-8601 timestamp"
        }
      ],
      
      "tags": {
        "gender": ["F4M", "F4F", "F4A"],
        "content": ["script-fill", "improv", "ramblefap"],
        "themes": ["gentle", "rough", "romantic"],
        "warnings": ["rape", "violence", "cnc"],
        "technical": ["binaural", "sfx", "music"]
      },
      
      "relationships": {
        "parent_audio_id": "parent_id_if_exists",
        "child_audio_ids": ["child1_id", "child2_id"],
        "series_info": {
          "series_id": "series_identifier",
          "position": 2,
          "total_parts": 5
        },
        "branch_info": {
          "choice_text": "Enter the door marked 'The Labs'",
          "branch_type": "story_choice|ending|alternate_version"
        }
      }
    }
  ],
  
  "enrichment_sources": [
    {
      "source_id": "unique_source_id",
      "platform": "Reddit|Patreon|HotAudio|GWASI",
      "url": "source_url",
      "post_id": "platform_specific_id",
      "author": "post_author_username",
      "title": "Original Post Title",
      "body": "Post body content",
      "extracted_at": "ISO-8601 timestamp",
      "extraction_method": "api|scrape|manual",
      
      "llm_analysis": {
        "model": "gpt-4|claude",
        "analyzed_at": "ISO-8601 timestamp",
        "extracted_data": {
          "performers": ["list", "of", "identified", "performers"],
          "series_detection": {
            "is_series": true|false,
            "series_name": "Series Name",
            "part_number": 2
          },
          "content_analysis": {
            "themes": ["identified", "themes"],
            "warnings": ["content", "warnings"],
            "summary": "Brief summary"
          }
        },
        "confidence_scores": {
          "performer_extraction": 0.95,
          "series_detection": 0.80
        }
      }
    }
  ],
  
  "aggregation_metadata": {
    "primary_source": "Reddit|HotAudio|Patreon",
    "total_audios": 25,
    "unique_performers": 16,
    "unique_writers": 12,
    "structure_type": "interactive_story|series|single|compilation",
    "has_branching": true,
    "max_branch_depth": 10,
    "tags_aggregated": ["all", "unique", "tags"],
    "total_duration_minutes": 245,
    "date_range": {
      "earliest": "2024-01-01",
      "latest": "2024-12-31"
    }
  }
}
```

## Implementation Recommendations

### 1. Migration Strategy

#### Phase 1: Data Structure Migration
```python
def migrate_to_v2(old_data):
    """Convert v1 analysis_results to v2 structure"""
    v2_data = {
        "release": {
            "id": generate_release_id(old_data),
            "title": extract_title(old_data),
            "type": determine_release_type(old_data),
            "version": "2.0"
        },
        "audios": [],
        "enrichment_sources": []
    }
    
    # Convert each audio_version to an audio entity
    for version in old_data.get("audio_versions", []):
        audio = create_audio_entity(version, old_data)
        v2_data["audios"].append(audio)
    
    return v2_data
```

#### Phase 2: Enrichment Enhancement
- Re-analyze existing Reddit posts with updated prompts
- Extract per-audio metadata where possible
- Identify relationships between audios

#### Phase 3: Validation
- Ensure no data loss during migration
- Verify all relationships are properly mapped
- Test with complex examples (LUST Project)

### 2. Processing Pipeline Updates

#### Update Extractor Components
```python
class ImprovedRedditExtractor:
    def extract_audio_entities(self, post_content):
        """Extract individual audio entities from post"""
        audios = []
        
        # Parse audio links with their context
        for audio_link in find_audio_links(post_content):
            audio = {
                "url": audio_link.url,
                "context": extract_surrounding_text(audio_link),
                "performers": extract_nearby_performers(audio_link),
                "tags": extract_nearby_tags(audio_link)
            }
            audios.append(audio)
        
        return audios
```

#### Update Analysis Prompts
```python
IMPROVED_ANALYSIS_PROMPT = """
Analyze this Reddit post and extract:

1. Individual Audio Entities:
   - Each audio link and its specific context
   - Performers mentioned near each audio
   - Version information (F4M, M4F, SFX, etc.)

2. Relationships:
   - Is this part of a series? Which part?
   - Are there alternate versions?
   - Any references to other audios?

3. Attribution:
   - Script writer (if mentioned)
   - Voice actors (may be different per audio)
   - Editors, mixers, other contributors

Return structured JSON with separate entries for each audio.
"""
```

### 3. Storage Optimizations

#### Directory Structure
```
data/
├── releases/
│   ├── release_id/
│   │   ├── release.json        # Complete v2 structure
│   │   ├── audios/
│   │   │   ├── audio1_id/
│   │   │   │   ├── audio.m4a
│   │   │   │   ├── metadata.json
│   │   │   │   └── transcript.txt
│   │   │   └── audio2_id/
│   │   └── enrichment/
│   │       ├── reddit_post.json
│   │       ├── patreon_post.json
│   │       └── hotaudio_tree.json
```

#### Database Schema (Optional)
```sql
-- Core tables
CREATE TABLE releases (
    id VARCHAR PRIMARY KEY,
    title TEXT,
    type VARCHAR,
    created_at TIMESTAMP
);

CREATE TABLE audios (
    id VARCHAR PRIMARY KEY,
    release_id VARCHAR REFERENCES releases(id),
    title TEXT,
    duration INTEGER,
    published_date DATE
);

CREATE TABLE performers (
    id VARCHAR PRIMARY KEY,
    name VARCHAR UNIQUE,
    platform_profile TEXT
);

-- Relationship tables
CREATE TABLE audio_performers (
    audio_id VARCHAR REFERENCES audios(id),
    performer_id VARCHAR REFERENCES performers(id),
    role VARCHAR,
    is_primary BOOLEAN
);

CREATE TABLE audio_relationships (
    parent_id VARCHAR REFERENCES audios(id),
    child_id VARCHAR REFERENCES audios(id),
    relationship_type VARCHAR,
    context TEXT
);
```

### 4. API Considerations

#### Backwards Compatibility
```python
class DataAccessLayer:
    def get_release(self, release_id, version="2.0"):
        """Get release data in requested version format"""
        data = load_release(release_id)
        
        if version == "1.0" and data.get("version") == "2.0":
            return convert_v2_to_v1(data)
        elif version == "2.0" and not data.get("version"):
            return migrate_to_v2(data)
        
        return data
```

#### Query Capabilities
```python
class ReleaseQuery:
    def find_by_performer(self, performer_name):
        """Find all audios by a specific performer"""
        
    def find_by_series(self, series_name):
        """Find all audios in a series, properly ordered"""
        
    def find_related_audios(self, audio_id):
        """Find parent, children, and series siblings"""
```

## Benefits of New Structure

### 1. Accurate Attribution
- Every contributor is properly credited
- Role-based attribution (voice, script, edit)
- No loss of performer information

### 2. Better Discovery
- Search by individual performer
- Find all audios in a series
- Navigate branching stories

### 3. Flexibility
- Supports simple singles and complex narratives
- Easy to add new metadata types
- Platform-agnostic design

### 4. Data Integrity
- Complete audit trail
- Source tracking for all metadata
- Checksums for downloaded files

## Migration Timeline

### Week 1-2: Development
- Implement v2 data structures
- Create migration utilities
- Update extractors

### Week 3: Testing
- Migrate sample data
- Test with complex examples
- Validate data integrity

### Week 4: Rollout
- Migrate existing data
- Update documentation
- Deploy new extractors

## Conclusion

The recommended data structure better reflects the reality of audio release complexity. By treating each audio as a first-class entity with its own metadata, we can properly handle:

1. Multi-performer collaborations
2. Interactive and branching stories
3. Series with complex relationships
4. Proper attribution for all contributors

This structure will make Aural more accurate, flexible, and useful for organizing audio content.