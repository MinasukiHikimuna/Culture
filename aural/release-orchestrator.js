/**
 * Release Orchestrator
 *
 * Coordinates the entire release extraction workflow:
 * 1. Discovery (Reddit/Patreon posts)
 * 2. Analysis (LLM enrichment)
 * 3. Audio extraction (platform-agnostic)
 * 4. Release aggregation
 * 5. Storage organization
 *
 * All files are stored directly in data/releases/{performer}/{release_dir}/
 */

const fs = require('fs').promises;
const path = require('path');
const crypto = require('crypto');

/**
 * Unified audio source schema
 */
class AudioSource {
  constructor(data = {}) {
    // Core audio data
    this.audio = {
      sourceUrl: data.sourceUrl || null,
      downloadUrl: data.downloadUrl || null,
      filePath: data.filePath || null,
      format: data.format || null,
      fileSize: data.fileSize || null,
      checksum: data.checksum || {}
    };
    
    // Metadata
    this.metadata = {
      title: data.title || null,
      author: data.author || null,
      description: data.description || null,
      tags: data.tags || [],
      duration: data.duration || null,
      uploadDate: data.uploadDate || null,
      extractedAt: data.extractedAt || new Date().toISOString(),
      platform: {
        name: data.platformName || null,
        extractorVersion: data.extractorVersion || null
      }
    };
    
    // Platform-specific data
    this.platformData = data.platformData || {};
    
    // Backup files
    this.backupFiles = {
      html: data.htmlBackup || null,
      metadata: data.metadataFile || null
    };
  }
}

/**
 * Release - aggregates multiple audio sources and enrichment data
 */
class Release {
  constructor(data = {}) {
    this.id = data.id || this.generateId();
    this.title = data.title || null;
    this.primaryPerformer = data.primaryPerformer || null;
    this.additionalPerformers = data.additionalPerformers || [];
    this.scriptAuthor = data.scriptAuthor || null;
    this.releaseDate = data.releaseDate || null;
    
    // Enrichment data from posts
    this.enrichmentData = {
      reddit: data.redditPost || null,
      patreon: data.patreonPost || null,
      llmAnalysis: data.llmAnalysis || null,
      gwasi: data.gwasiData || null
    };
    
    // Audio sources - platform-agnostic array
    this.audioSources = data.audioSources || [];
    
    // Script data
    this.script = data.script || null;
    
    // Artwork
    this.artwork = data.artwork || [];
    
    // Aggregation metadata
    this.aggregatedAt = data.aggregatedAt || new Date().toISOString();
    this.version = data.version || '1.0';
  }
  
  generateId() {
    const data = `${this.title}-${this.primaryPerformer}-${Date.now()}`;
    return crypto.createHash('sha256').update(data).digest('hex').substring(0, 16);
  }
  
  /**
   * Add an audio source to the release
   */
  addAudioSource(audioSource) {
    this.audioSources.push(audioSource);
  }
  
  /**
   * Get audio sources by platform
   */
  getAudioSourcesByPlatform(platformName) {
    return this.audioSources.filter(
      source => source.metadata.platform.name === platformName
    );
  }
  
  /**
   * Check if release has all expected audio variants
   */
  hasAllVariants(expectedVariants = ['M4F', 'F4M']) {
    const foundVariants = new Set();
    
    // Check tags and descriptions for variant indicators
    for (const source of this.audioSources) {
      const allText = [
        source.metadata.title,
        source.metadata.description,
        ...source.metadata.tags
      ].join(' ').toUpperCase();
      
      for (const variant of expectedVariants) {
        if (allText.includes(variant)) {
          foundVariants.add(variant);
        }
      }
    }
    
    return expectedVariants.every(v => foundVariants.has(v));
  }
}

/**
 * Main orchestrator class
 */
class ReleaseOrchestrator {
  constructor(config = {}) {
    this.config = {
      dataDir: config.dataDir || 'data',
      validateExtractions: config.validateExtractions !== false,
      ...config
    };

    // Platform extractors registry
    this.extractors = new Map();

    // Initialize default extractors
    this.registerExtractor('soundgasm', {
      pattern: /soundgasm\.net/i,
      module: './soundgasm-extractor.js'
    });

    this.registerExtractor('whypit', {
      pattern: /whyp\.it/i,
      module: './whypit-extractor.js'
    });

    this.registerExtractor('hotaudio', {
      pattern: /hotaudio\.net/i,
      module: './hotaudio-extractor.js'
    });

    // Track active extractor instances for cleanup
    this.activeExtractors = new Map();
  }

  /**
   * Register a platform extractor
   */
  registerExtractor(platform, config) {
    this.extractors.set(platform, config);
  }

  /**
   * Get appropriate extractor for a URL
   */
  getExtractorForUrl(url) {
    for (const [platform, config] of this.extractors) {
      if (config.pattern.test(url)) {
        return { platform, config };
      }
    }
    return null;
  }

  /**
   * Extract audio from URL directly to target path
   * @param {string} url - Audio URL to extract
   * @param {object} targetPath - Target paths for output files
   * @param {string} targetPath.dir - Directory to save files
   * @param {string} targetPath.basename - Base filename (without extension)
   */
  async extractAudio(url, targetPath) {
    // Find appropriate extractor
    const extractorInfo = this.getExtractorForUrl(url);
    if (!extractorInfo) {
      throw new Error(`No extractor found for URL: ${url}`);
    }

    const { platform, config } = extractorInfo;
    console.log(`🔧 Using ${platform} extractor for: ${url}`);

    try {
      // Get or create extractor instance
      let extractor = this.activeExtractors.get(platform);
      if (!extractor) {
        const ExtractorClass = require(config.module);
        extractor = new ExtractorClass({ requestDelay: 2000 });

        if (extractor.setupPlaywright) {
          await extractor.setupPlaywright();
        }

        this.activeExtractors.set(platform, extractor);
      }

      // Extract audio directly to target path
      const result = await extractor.extract(url, targetPath);

      // Transform to AudioSource
      const audioSource = this.normalizeExtractorResult(result, platform);

      return audioSource;

    } catch (error) {
      console.error(`❌ Extraction failed for ${url}: ${error.message}`);
      throw error;
    }
  }

  /**
   * Cleanup all active extractors
   */
  async cleanup() {
    for (const [platform, extractor] of this.activeExtractors) {
      if (extractor.closeBrowser) {
        await extractor.closeBrowser();
        console.log(`🔒 Closed ${platform} extractor`);
      }
    }
    this.activeExtractors.clear();
  }
  
  /**
   * Normalize extractor results to unified schema
   */
  normalizeExtractorResult(result, platform) {
    // If already in correct format, return as-is
    if (result instanceof AudioSource) {
      return result;
    }
    
    // Transform from new extractor format to AudioSource schema
    const audioSource = new AudioSource({
      sourceUrl: result.audio?.sourceUrl || result.sourceUrl || result.url,
      downloadUrl: result.audio?.downloadUrl || result.audioUrl,
      filePath: result.audio?.filePath || result.filePath,
      format: result.audio?.format || result.format || 'm4a',
      fileSize: result.audio?.fileSize || result.fileSize,
      checksum: result.audio?.checksum || result.checksum || {},
      
      title: result.metadata?.title || result.title,
      author: result.metadata?.author || result.author || result.user,
      description: result.metadata?.description || result.description,
      tags: result.metadata?.tags || result.tags || [],
      duration: result.metadata?.duration || result.duration,
      uploadDate: result.metadata?.uploadDate || result.uploadDate,
      
      platformName: platform,
      extractorVersion: result.metadata?.platform?.extractorVersion || '1.0',
      platformData: result.platformData || {},
      
      htmlBackup: result.backupFiles?.html || result.htmlBackup,
      metadataFile: result.backupFiles?.metadata || result.metadataFile
    });
    
    return audioSource;
  }
  
  /**
   * Process a Reddit/Patreon post into a release
   */
  async processPost(post, llmAnalysis = null) {
    console.log(`🎯 Processing post: ${post.title}`);

    // Determine target directory structure first (before creating release)
    let releaseDir;
    if (llmAnalysis?.version_naming?.release_directory) {
      releaseDir = path.join(
        this.config.dataDir,
        'releases',
        post.author,
        llmAnalysis.version_naming.release_directory
      );
    } else {
      // Generate a stable ID based on post ID for fallback
      const stableId = post.id || crypto.createHash('sha256')
        .update(`${post.title}-${post.author}`)
        .digest('hex')
        .substring(0, 16);
      releaseDir = path.join(
        this.config.dataDir,
        'releases',
        post.author,
        stableId
      );
    }

    // Check if release already exists
    const releasePath = path.join(releaseDir, 'release.json');
    try {
      await fs.access(releasePath);
      // Release exists - load and return it
      const existingData = await fs.readFile(releasePath, 'utf8');
      const existingRelease = JSON.parse(existingData);
      console.log(`⏭️  Release already exists: ${releaseDir}`);
      console.log(`   Audio sources: ${existingRelease.audioSources?.length || 0}`);

      // Return a Release object with the existing data
      const release = new Release(existingRelease);
      release.id = existingRelease.id;
      release.audioSources = existingRelease.audioSources || [];
      return release;
    } catch {
      // Release doesn't exist, proceed with creation
    }

    // Create release object
    const release = new Release({
      title: post.title,
      primaryPerformer: post.author,
      releaseDate: post.created_utc,
      redditPost: post,
      llmAnalysis: llmAnalysis
    });

    await fs.mkdir(releaseDir, { recursive: true });

    // Extract audio URLs from post and analysis
    const audioUrls = this.extractAudioUrls(post, llmAnalysis);
    console.log(`🔗 Found ${audioUrls.length} audio URLs`);

    // Process each audio version with proper naming
    if (llmAnalysis?.audio_versions && llmAnalysis.audio_versions.length > 0) {
      for (let i = 0; i < llmAnalysis.audio_versions.length; i++) {
        const audioVersion = llmAnalysis.audio_versions[i];

        if (audioVersion.urls && audioVersion.urls.length > 0) {
          for (const urlInfo of audioVersion.urls) {
            try {
              console.log(`📥 Extracting: ${urlInfo.url} (${audioVersion.version_name || `Version ${i+1}`})`);

              // Determine basename for this version
              const basename = audioVersion.filename
                ? audioVersion.filename.replace(/\.[^.]+$/, '') // Remove extension
                : `${llmAnalysis.version_naming?.release_slug || release.id}_${audioVersion.slug || i}`;

              const targetPath = { dir: releaseDir, basename };
              const audioSource = await this.extractAudio(urlInfo.url, targetPath);

              // Add version-specific metadata
              audioSource.versionInfo = {
                slug: audioVersion.slug,
                version_name: audioVersion.version_name,
                description: audioVersion.description
              };

              release.addAudioSource(audioSource);
              console.log(`✅ Added audio source: ${audioVersion.version_name || 'Version'} from ${audioSource.metadata.platform.name}`);

            } catch (error) {
              console.error(`❌ Failed to extract ${urlInfo.url}: ${error.message}`);
              // Continue with other URLs
            }
          }
        }
      }
    } else {
      // Fallback: process URLs directly (old method)
      for (let i = 0; i < audioUrls.length; i++) {
        const url = audioUrls[i];
        try {
          console.log(`📥 Extracting: ${url}`);

          const basename = `${release.id}_audio_${i}`;
          const targetPath = { dir: releaseDir, basename };
          const audioSource = await this.extractAudio(url, targetPath);

          release.addAudioSource(audioSource);
          console.log(`✅ Added audio source from ${audioSource.metadata.platform.name}`);
        } catch (error) {
          console.error(`❌ Failed to extract ${url}: ${error.message}`);
          // Continue with other URLs
        }
      }
    }

    // Extract script if available
    if (llmAnalysis?.script_url) {
      try {
        release.script = await this.extractScript(llmAnalysis.script_url);
      } catch (error) {
        console.error(`❌ Failed to extract script: ${error.message}`);
      }
    }

    // Save release
    await this.saveRelease(release);

    // Cleanup extractors
    await this.cleanup();

    console.log(`✅ Release processed: ${release.id}`);
    return release;
  }
  
  /**
   * Extract audio URLs from post and analysis
   */
  extractAudioUrls(post, llmAnalysis) {
    const urls = new Set();
    
    // From post content
    const urlRegex = /https?:\/\/(?:www\.)?(soundgasm\.net|whyp\.it|hotaudio\.net)[^\s\]]+/gi;
    const postUrls = (post.content || post.selftext || '').match(urlRegex) || [];
    postUrls.forEach(url => urls.add(url));
    
    // From LLM analysis
    if (llmAnalysis?.audio_versions) {
      for (const version of llmAnalysis.audio_versions) {
        if (version.urls) {
          version.urls.forEach(urlInfo => urls.add(urlInfo.url));
        }
      }
    }
    
    return Array.from(urls);
  }
  
  /**
   * Extract script (placeholder - implement later)
   */
  async extractScript(scriptUrl) {
    console.log(`📝 Script extraction not yet implemented: ${scriptUrl}`);
    return null;
  }
  
  /**
   * Save release to storage using new naming structure
   */
  async saveRelease(release) {
    // Use version naming if available, otherwise fallback to old structure
    let releaseDir;
    
    if (release.enrichmentData?.llmAnalysis?.version_naming?.release_directory) {
      // Use new naming structure: data/releases/performer/release_directory/
      releaseDir = path.join(
        this.config.dataDir,
        'releases',
        release.primaryPerformer,
        release.enrichmentData.llmAnalysis.version_naming.release_directory
      );
    } else {
      // Fallback to old structure
      releaseDir = path.join(
        this.config.dataDir,
        'releases',
        release.primaryPerformer,
        release.id
      );
    }
    
    await fs.mkdir(releaseDir, { recursive: true });
    
    // Save release metadata in the same directory as audio files
    const releasePath = path.join(releaseDir, 'release.json');
    await fs.writeFile(releasePath, JSON.stringify(release, null, 2));
    
    // Update release index
    await this.updateReleaseIndex(release);
    
    console.log(`💾 Release saved: ${releasePath}`);
  }
  
  /**
   * Update global release index
   */
  async updateReleaseIndex(release) {
    const indexPath = path.join(this.config.dataDir, 'releases', 'index.json');
    
    let index = { releases: [] };
    try {
      const existing = await fs.readFile(indexPath, 'utf8');
      index = JSON.parse(existing);
    } catch {
      // Index doesn't exist yet
    }
    
    // Add or update release in index
    const existingIndex = index.releases.findIndex(r => r.id === release.id);
    const indexEntry = {
      id: release.id,
      title: release.title,
      primaryPerformer: release.primaryPerformer,
      audioSourceCount: release.audioSources.length,
      platforms: [...new Set(release.audioSources.map(s => s.metadata.platform.name))],
      aggregatedAt: release.aggregatedAt
    };
    
    if (existingIndex >= 0) {
      index.releases[existingIndex] = indexEntry;
    } else {
      index.releases.push(indexEntry);
    }
    
    await fs.writeFile(indexPath, JSON.stringify(index, null, 2));
  }
  
  /**
   * Validate extraction results
   */
  async validateExtraction(audioSource) {
    if (!this.config.validateExtractions) return true;
    
    const validations = {
      hasFile: !!audioSource.audio.filePath,
      hasTitle: !!audioSource.metadata.title,
      hasAuthor: !!audioSource.metadata.author,
      hasChecksum: !!audioSource.audio.checksum?.sha256,
      fileExists: false
    };
    
    // Check if file exists
    if (audioSource.audio.filePath) {
      try {
        await fs.access(audioSource.audio.filePath);
        validations.fileExists = true;
      } catch {
        validations.fileExists = false;
      }
    }
    
    const isValid = Object.values(validations).every(v => v === true);
    
    if (!isValid) {
      console.warn('⚠️  Validation warnings:', validations);
    }
    
    return isValid;
  }
}

module.exports = {
  ReleaseOrchestrator,
  Release,
  AudioSource
};