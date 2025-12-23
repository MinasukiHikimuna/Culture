# Improved Data Structure for Audio Releases

## Problem with Current Structure

The current `analysis_results` structure incorrectly assumes:
- One set of performers for the entire release
- One script shared by all audio versions
- A flat structure of audio variants

## Reality (from HotAudio LUST Project)

The HotAudio story-tree.json reveals that:
- Each audio has its own performers (different voice actors)
- Each audio has its own script (different writers)
- Multiple performers can collaborate on a single audio
- Audios can have complex relationships (branching narratives)

## Proposed Improved Structure

```json
{
  "release": {
    "id": "unique_release_id",
    "title": "Overall Release Title",
    "type": "single|series|interactive|compilation",
    "created_at": "2025-08-04T04:28:56.354Z",
    "updated_at": "2025-08-04T04:28:56.354Z"
  },
  
  "audios": [
    {
      "audio_id": "unique_audio_id",
      "title": "Individual Audio Title",
      "description": "Audio description",
      "duration": "24m",
      "published_date": "2024-11-07",
      
      "performers": [
        {
          "name": "VoidScreamsBack",
          "role": "voice",
          "primary": true
        },
        {
          "name": "MyAuralFixation", 
          "role": "editor",
          "primary": false
        }
      ],
      
      "script": {
        "url": "https://scriptbin.works/u/author/script",
        "author": "Kinkystuff420",
        "fill_type": "public|private|original"
      },
      
      "files": [
        {
          "platform": "Soundgasm",
          "url": "https://soundgasm.net/u/performer/audio",
          "filename": "release_id_audio_title.m4a",
          "metadata_file": "release_id_audio_title.json",
          "checksum": "sha256_hash"
        }
      ],
      
      "tags": ["F4M", "NSFW", "Fdom", "specific_content_tags"],
      
      "relationships": {
        "parent_audio_id": "L1-First-Meeting",
        "child_audio_ids": ["L1-First-Meeting", "T1-Wake-Up"],
        "branch_context": "Enter the door marked \"The Labs\"",
        "series_position": null
      },
      
      "metadata": {
        "credits": {
          "by": ["The_LUST_Project"],
          "script": ["Kinkystuff420"],
          "voice": ["VoidScreamsBack"],
          "edit": ["MyAuralFixation"]
        }
      }
    }
  ],
  
  "enrichment_sources": [
    {
      "platform": "Reddit",
      "url": "https://www.reddit.com/r/gonewildaudio/comments/post_id/",
      "post_id": "post_id",
      "author": "reddit_username",
      "title": "Reddit Post Title",
      "extracted_at": "2025-08-04T04:28:56.354Z",
      "llm_analysis": {
        "performers_mentioned": ["performer1", "performer2"],
        "series_detection": {},
        "content_warnings": [],
        "analysis_metadata": {}
      }
    },
    {
      "platform": "HotAudio",
      "url": "https://hotaudio.net/u/user/audio",
      "story_tree": "path/to/story-tree.json",
      "extracted_at": "2025-08-04T04:28:56.354Z"
    }
  ],
  
  "aggregation_metadata": {
    "primary_source": "Reddit|HotAudio|Patreon",
    "total_audios": 25,
    "total_performers": 16,
    "structure_type": "interactive_story|series|single|compilation",
    "has_branching": true,
    "max_depth": 10
  }
}
```

## Key Improvements

1. **Audio-Centric Model**: Each audio is a first-class entity with its own metadata
2. **Flexible Performer Attribution**: Multiple performers per audio with roles
3. **Script Per Audio**: Each audio can have its own script/writer
4. **Relationship Tracking**: Parent/child relationships for branching narratives
5. **Multiple File Sources**: Same audio from different platforms
6. **Enrichment Sources**: Track where metadata came from
7. **Credits Preservation**: Maintain full credit information per audio

## Migration Considerations

When migrating from the old structure:
1. Split `audio_versions` into individual `audios` entries
2. Duplicate shared metadata (performers, script) to each audio that uses it
3. Preserve all enrichment data and LLM analysis
4. Add relationship tracking for series/branching content
5. Maintain backward compatibility with a version field

## Example: Simple Release

```json
{
  "release": {
    "id": "1lxhwbd_catching_shy_girl",
    "title": "Catching A Shy, Touch-Starved Girl Masturbating",
    "type": "single"
  },
  "audios": [
    {
      "audio_id": "1lxhwbd_main",
      "title": "Catching A Shy, Touch-Starved Girl Masturbating In Your Bed",
      "performers": [
        {"name": "alekirser", "role": "voice", "primary": true}
      ],
      "script": {
        "url": "https://www.reddit.com/r/gonewildaudio/comments/uotcc0/",
        "author": "DestinyEvolved",
        "fill_type": "public"
      },
      "files": [
        {
          "platform": "Soundgasm",
          "url": "https://soundgasm.net/u/alekirser/F4M-Catching...",
          "filename": "1lxhwbd_catching_shy_girl.m4a"
        }
      ]
    }
  ]
}
```

## Example: Complex Interactive Release

See the LUST Project structure where:
- 30+ interconnected audios
- Different performers for each segment
- Branching narrative paths
- Multiple writers contributing scripts
- Complex parent/child relationships