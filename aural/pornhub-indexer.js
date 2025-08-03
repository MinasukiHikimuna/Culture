#!/usr/bin/env node

/**
 * Pornhub Video Indexer
 * 
 * This script extracts metadata from Pornhub videos using yt-dlp without downloading them.
 * It creates a comprehensive JSON index similar to what gwasi_extractor.py does for Reddit data.
 * 
 * Features:
 * - Extract video metadata using yt-dlp --simulate
 * - Cache intermediate results to avoid re-processing
 * - Generate comprehensive JSON output with video information
 * - Support for individual URLs or user profile indexing
 * 
 * Usage:
 *   node pornhub-indexer.js --url "https://pornhub.com/view_video.php?viewkey=..."
 *   node pornhub-indexer.js --user "username" --max-videos 100
 *   node pornhub-indexer.js --playlist "playlist_url"
 */

const fs = require('fs').promises;
const path = require('path');
const { spawn } = require('child_process');
const crypto = require('crypto');

class PornhubIndexer {
    constructor(options = {}) {
        this.outputDir = options.outputDir || 'pornhub_data';
        this.cacheDir = path.join(this.outputDir, 'cache');
        this.maxRetries = options.maxRetries || 3;
        this.retryDelay = options.retryDelay || 1000;
        this.useCache = options.useCache !== false;
        
        // Create output directories
        this.initDirectories();
    }

    async initDirectories() {
        try {
            await fs.mkdir(this.outputDir, { recursive: true });
            await fs.mkdir(this.cacheDir, { recursive: true });
            console.log(`📁 Output directory: ${this.outputDir}`);
            console.log(`📂 Cache directory: ${this.cacheDir}`);
        } catch (error) {
            console.error('❌ Failed to create directories:', error.message);
            throw error;
        }
    }

    /**
     * Generate cache key for a URL
     */
    getCacheKey(url) {
        return crypto.createHash('md5').update(url).digest('hex');
    }

    /**
     * Get cache file path for a URL
     */
    getCacheFilePath(url) {
        const key = this.getCacheKey(url);
        return path.join(this.cacheDir, `${key}.json`);
    }

    /**
     * Load cached metadata for a URL
     */
    async loadFromCache(url) {
        if (!this.useCache) return null;

        const cacheFile = this.getCacheFilePath(url);
        try {
            const data = await fs.readFile(cacheFile, 'utf8');
            const parsed = JSON.parse(data);
            console.log(`📂 Loaded from cache: ${url}`);
            return parsed;
        } catch (error) {
            // Cache miss or invalid cache file
            return null;
        }
    }

    /**
     * Save metadata to cache
     */
    async saveToCache(url, metadata) {
        if (!this.useCache) return;

        const cacheFile = this.getCacheFilePath(url);
        try {
            await fs.writeFile(cacheFile, JSON.stringify(metadata, null, 2));
            console.log(`💾 Cached metadata for: ${url}`);
        } catch (error) {
            console.warn('⚠️  Failed to save to cache:', error.message);
        }
    }

    /**
     * Execute yt-dlp command with retry logic
     */
    async executeYtDlp(url, options = []) {
        const defaultOptions = [
            '--simulate',
            '--dump-json',
            '--no-warnings',
            '--extractor-retries', '3'
        ];

        const command = 'yt-dlp';
        const args = [...defaultOptions, ...options, url];

        for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
            try {
                console.log(`📥 Extracting metadata (attempt ${attempt}/${this.maxRetries}): ${url}`);
                
                const result = await new Promise((resolve, reject) => {
                    let stdout = '';
                    let stderr = '';

                    const process = spawn(command, args, {
                        stdio: ['pipe', 'pipe', 'pipe']
                    });

                    process.stdout.on('data', (data) => {
                        stdout += data.toString();
                    });

                    process.stderr.on('data', (data) => {
                        stderr += data.toString();
                    });

                    process.on('close', (code) => {
                        if (code === 0) {
                            resolve({ stdout, stderr });
                        } else {
                            reject(new Error(`yt-dlp exited with code ${code}: ${stderr}`));
                        }
                    });

                    process.on('error', (error) => {
                        reject(new Error(`Failed to spawn yt-dlp: ${error.message}`));
                    });
                });

                return result.stdout;

            } catch (error) {
                console.error(`❌ Attempt ${attempt} failed: ${error.message}`);
                
                if (attempt === this.maxRetries) {
                    throw error;
                }

                // Wait before retry
                await new Promise(resolve => setTimeout(resolve, this.retryDelay * attempt));
            }
        }
    }

    /**
     * Extract metadata from a single video URL
     */
    async extractVideoMetadata(url) {
        // Check cache first
        const cached = await this.loadFromCache(url);
        if (cached) {
            return cached;
        }

        try {
            const jsonOutput = await this.executeYtDlp(url);
            
            // Parse each line as separate JSON (yt-dlp outputs one JSON per line)
            const lines = jsonOutput.trim().split('\n').filter(line => line.trim());
            const metadata = [];

            for (const line of lines) {
                try {
                    const videoData = JSON.parse(line);
                    const processedData = this.processVideoData(videoData);
                    metadata.push(processedData);
                } catch (parseError) {
                    console.warn('⚠️  Failed to parse JSON line:', parseError.message);
                }
            }

            // Cache the results
            if (metadata.length > 0) {
                await this.saveToCache(url, metadata);
            }

            return metadata;

        } catch (error) {
            console.error(`❌ Failed to extract metadata from ${url}:`, error.message);
            return [];
        }
    }

    /**
     * Process raw video data from yt-dlp into standardized format
     */
    processVideoData(rawData) {
        const processed = {
            // Basic identifiers
            id: rawData.id,
            title: rawData.title,
            url: rawData.webpage_url,
            original_url: rawData.original_url,
            
            // Uploader information
            uploader: rawData.uploader,
            uploader_id: rawData.uploader_id,
            uploader_url: rawData.uploader_url,
            
            // Video metadata
            duration: rawData.duration,
            duration_string: rawData.duration_string,
            view_count: rawData.view_count,
            like_count: rawData.like_count,
            dislike_count: rawData.dislike_count,
            comment_count: rawData.comment_count,
            
            // Content information
            description: rawData.description,
            tags: rawData.tags || [],
            categories: rawData.categories || [],
            
            // Upload information
            upload_date: rawData.upload_date,
            timestamp: rawData.timestamp,
            
            // Quality and format information
            width: rawData.width,
            height: rawData.height,
            fps: rawData.fps,
            resolution: rawData.resolution,
            format_id: rawData.format_id,
            ext: rawData.ext,
            
            // Thumbnail
            thumbnail: rawData.thumbnail,
            thumbnails: rawData.thumbnails || [],
            
            // Additional metadata
            age_limit: rawData.age_limit,
            availability: rawData.availability,
            
            // Processing metadata
            extraction_date: new Date().toISOString(),
            extractor: rawData.extractor,
            extractor_key: rawData.extractor_key
        };

        // Add derived fields
        processed.content_type = this.determineContentType(processed);
        processed.quality_tier = this.determineQualityTier(processed);
        processed.performer_info = this.extractPerformerInfo(processed);

        return processed;
    }

    /**
     * Determine content type based on title and tags
     */
    determineContentType(videoData) {
        const title = (videoData.title || '').toLowerCase();
        const tags = (videoData.tags || []).map(tag => tag.toLowerCase());
        const categories = (videoData.categories || []).map(cat => cat.toLowerCase());

        const allText = [title, ...tags, ...categories].join(' ');

        // Define content type patterns
        const contentTypes = {
            'amateur': /amateur|homemade|real couple|private/,
            'professional': /brazzers|reality kings|naughty america|professional/,
            'cam': /cam|webcam|chaturbate|streamate/,
            'compilation': /compilation|best of|collection/,
            'music_video': /music|pmv|compilation/,
            'tutorial': /tutorial|how to|educational/,
            'verification': /verification|verify/
        };

        for (const [type, pattern] of Object.entries(contentTypes)) {
            if (pattern.test(allText)) {
                return type;
            }
        }

        return 'standard';
    }

    /**
     * Determine quality tier based on resolution and other factors
     */
    determineQualityTier(videoData) {
        const height = videoData.height || 0;
        
        if (height >= 2160) return '4K';
        if (height >= 1440) return '1440p';
        if (height >= 1080) return '1080p';
        if (height >= 720) return '720p';
        if (height >= 480) return '480p';
        if (height >= 360) return '360p';
        if (height >= 240) return '240p';
        
        return 'unknown';
    }

    /**
     * Extract performer information from title and metadata
     */
    extractPerformerInfo(videoData) {
        const title = videoData.title || '';
        const uploader = videoData.uploader || '';
        
        // Basic performer extraction (could be enhanced with more sophisticated parsing)
        const performers = {
            primary: uploader,
            detected: [],
            verified: false
        };

        // Look for common performer name patterns in title
        // This is a basic implementation - could be made more sophisticated
        const namePatterns = [
            /featuring\s+([^,]+)/gi,
            /with\s+([^,]+)/gi,
            /starring\s+([^,]+)/gi
        ];

        for (const pattern of namePatterns) {
            const matches = title.matchAll(pattern);
            for (const match of matches) {
                if (match[1]) {
                    performers.detected.push(match[1].trim());
                }
            }
        }

        return performers;
    }

    /**
     * Detect URL type and route to appropriate extraction method
     */
    async extractFromUrl(url, maxVideos = null) {
        const urlType = this.detectUrlType(url);
        
        switch (urlType) {
            case 'video':
                console.log('🎥 Detected single video URL');
                return await this.extractVideoMetadata(url);
            
            case 'user':
            case 'channel':
                console.log(`👤 Detected ${urlType} URL`);
                return await this.extractChannelVideos(url, maxVideos);
            
            case 'playlist':
                console.log('📋 Detected playlist URL');
                return await this.extractPlaylistVideos(url, maxVideos);
            
            default:
                console.log('🔍 Unknown URL type, attempting generic extraction');
                return await this.extractChannelVideos(url, maxVideos);
        }
    }

    /**
     * Detect the type of Pornhub URL
     */
    detectUrlType(url) {
        const urlLower = url.toLowerCase();
        
        if (urlLower.includes('/view_video.php') || urlLower.includes('/video/')) {
            return 'video';
        }
        
        if (urlLower.includes('/users/') || urlLower.includes('/user/')) {
            return 'user';
        }
        
        if (urlLower.includes('/channels/') || urlLower.includes('/channel/')) {
            return 'channel';
        }
        
        if (urlLower.includes('/playlist/') || urlLower.includes('list=')) {
            return 'playlist';
        }
        
        if (urlLower.includes('/model/') || urlLower.includes('/models/')) {
            return 'channel';
        }
        
        if (urlLower.includes('/pornstar/') || urlLower.includes('/pornstars/')) {
            return 'channel';
        }
        
        return 'unknown';
    }

    /**
     * Extract metadata from user profile/channel
     */
    async extractUserVideos(username, maxVideos = null) {
        const userUrl = `https://www.pornhub.com/users/${username}/videos`;
        return await this.extractChannelVideos(userUrl, maxVideos);
    }

    /**
     * Extract metadata from any channel/user/model URL
     */
    async extractChannelVideos(channelUrl, maxVideos = null) {
        console.log(`📺 Extracting videos from channel: ${channelUrl}`);

        const options = [
            '--flat-playlist',
            '--ignore-errors',
            '--no-warnings'
        ];
        
        if (maxVideos) {
            options.push('--playlist-end', maxVideos.toString());
        }

        try {
            const jsonOutput = await this.executeYtDlp(channelUrl, options);
            return await this.processPlaylistOutput(jsonOutput, 'channel');

        } catch (error) {
            console.error(`❌ Failed to extract channel videos from ${channelUrl}:`, error.message);
            return [];
        }
    }

    /**
     * Extract metadata from playlist URL
     */
    async extractPlaylistVideos(playlistUrl, maxVideos = null) {
        console.log(`📋 Extracting videos from playlist: ${playlistUrl}`);

        const options = [
            '--flat-playlist',
            '--ignore-errors',
            '--no-warnings'
        ];
        
        if (maxVideos) {
            options.push('--playlist-end', maxVideos.toString());
        }

        try {
            const jsonOutput = await this.executeYtDlp(playlistUrl, options);
            return await this.processPlaylistOutput(jsonOutput, 'playlist');

        } catch (error) {
            console.error(`❌ Failed to extract playlist videos from ${playlistUrl}:`, error.message);
            return [];
        }
    }

    /**
     * Process playlist/channel output and extract individual video metadata
     */
    async processPlaylistOutput(jsonOutput, sourceType = 'playlist') {
        const lines = jsonOutput.trim().split('\n').filter(line => line.trim());
        
        const videoUrls = [];
        let playlistInfo = null;

        for (const line of lines) {
            try {
                const data = JSON.parse(line);
                
                // Check if this is playlist metadata or a video entry
                if (data._type === 'playlist' || data.extractor === 'pornhub:playlist') {
                    playlistInfo = {
                        title: data.title,
                        id: data.id,
                        uploader: data.uploader,
                        description: data.description,
                        entry_count: data.playlist_count || data.entry_count
                    };
                    console.log(`📋 Found ${sourceType}: "${data.title}" with ${playlistInfo.entry_count || 'unknown'} videos`);
                } else if (data.url || data.webpage_url) {
                    // This is a video entry
                    const videoUrl = data.url || data.webpage_url;
                    videoUrls.push({
                        url: videoUrl,
                        title: data.title,
                        id: data.id,
                        duration: data.duration,
                        playlist_index: data.playlist_index
                    });
                }
            } catch (parseError) {
                console.warn('⚠️  Failed to parse JSON line:', parseError.message);
            }
        }

        console.log(`🔍 Found ${videoUrls.length} videos in ${sourceType}`);

        if (videoUrls.length === 0) {
            console.warn(`⚠️  No videos found in ${sourceType}`);
            return [];
        }

        // Extract metadata for each video
        const allMetadata = [];
        for (let i = 0; i < videoUrls.length; i++) {
            const videoEntry = videoUrls[i];
            console.log(`📥 Processing video ${i + 1}/${videoUrls.length}: ${videoEntry.title || videoEntry.url}`);
            
            try {
                const metadata = await this.extractVideoMetadata(videoEntry.url);
                
                // Add playlist/channel context to each video
                for (const video of metadata) {
                    video.source_type = sourceType;
                    video.playlist_info = playlistInfo;
                    video.playlist_index = videoEntry.playlist_index;
                    
                    if (sourceType === 'channel') {
                        video.channel_url = videoEntry.url.split('/view_video.php')[0];
                    }
                }
                
                allMetadata.push(...metadata);
            } catch (videoError) {
                console.error(`❌ Failed to extract metadata for video ${i + 1}: ${videoError.message}`);
                // Continue with next video instead of stopping
                continue;
            }

            // Small delay to be respectful to the server
            await new Promise(resolve => setTimeout(resolve, 500));
        }

        return allMetadata;
    }

    /**
     * Save extracted data to JSON file
     */
    async saveToJson(data, filename) {
        if (!data || data.length === 0) {
            console.warn('⚠️  No data to save');
            return;
        }

        const filepath = path.join(this.outputDir, filename);

        try {
            await fs.writeFile(filepath, JSON.stringify(data, null, 2));
            console.log(`💾 Saved ${data.length} entries to ${filepath}`);
        } catch (error) {
            console.error('❌ Error saving to JSON:', error.message);
            throw error;
        }
    }

    /**
     * Generate summary report
     */
    generateSummary(data) {
        if (!data || data.length === 0) {
            return null;
        }

        const summary = {
            total_videos: data.length,
            extraction_date: new Date().toISOString(),
            uploaders: {},
            content_types: {},
            quality_tiers: {},
            total_duration: 0,
            total_views: 0,
            date_range: { earliest: null, latest: null }
        };

        const uploadDates = [];

        for (const video of data) {
            // Count uploaders
            const uploader = video.uploader || 'unknown';
            summary.uploaders[uploader] = (summary.uploaders[uploader] || 0) + 1;

            // Count content types
            const contentType = video.content_type || 'unknown';
            summary.content_types[contentType] = (summary.content_types[contentType] || 0) + 1;

            // Count quality tiers
            const qualityTier = video.quality_tier || 'unknown';
            summary.quality_tiers[qualityTier] = (summary.quality_tiers[qualityTier] || 0) + 1;

            // Accumulate stats
            if (video.duration) summary.total_duration += video.duration;
            if (video.view_count) summary.total_views += video.view_count;

            // Collect upload dates
            if (video.upload_date) {
                uploadDates.push(video.upload_date);
            }
        }

        // Date range
        if (uploadDates.length > 0) {
            uploadDates.sort();
            summary.date_range.earliest = uploadDates[0];
            summary.date_range.latest = uploadDates[uploadDates.length - 1];
        }

        return summary;
    }

    /**
     * Print summary to console
     */
    printSummary(summary) {
        if (!summary) return;

        console.log('\n📈 EXTRACTION SUMMARY');
        console.log('='.repeat(50));
        console.log(`Total videos: ${summary.total_videos.toLocaleString()}`);
        console.log(`Total duration: ${Math.round(summary.total_duration / 60)} minutes`);
        console.log(`Total views: ${summary.total_views.toLocaleString()}`);
        console.log(`Date range: ${summary.date_range.earliest} to ${summary.date_range.latest}`);

        console.log('\nTop uploaders:');
        Object.entries(summary.uploaders)
            .sort(([,a], [,b]) => b - a)
            .slice(0, 10)
            .forEach(([uploader, count]) => {
                console.log(`  ${uploader}: ${count}`);
            });

        console.log('\nContent types:');
        Object.entries(summary.content_types)
            .sort(([,a], [,b]) => b - a)
            .forEach(([type, count]) => {
                console.log(`  ${type}: ${count}`);
            });

        console.log('\nQuality distribution:');
        Object.entries(summary.quality_tiers)
            .sort(([,a], [,b]) => b - a)
            .forEach(([quality, count]) => {
                console.log(`  ${quality}: ${count}`);
            });
    }
}

module.exports = PornhubIndexer;

// CLI functionality
if (require.main === module) {
    const args = process.argv.slice(2);
    
    const options = {
        outputDir: 'pornhub_data',
        useCache: true,
        maxRetries: 3
    };

    let url = null;
    let username = null;
    let channelUrl = null;
    let maxVideos = null;

    // Parse command line arguments
    for (let i = 0; i < args.length; i++) {
        const arg = args[i];
        
        if (arg === '--url' && i + 1 < args.length) {
            url = args[i + 1];
            i++;
        } else if (arg === '--user' && i + 1 < args.length) {
            username = args[i + 1];
            i++;
        } else if (arg === '--channel' && i + 1 < args.length) {
            channelUrl = args[i + 1];
            i++;
        } else if (arg === '--max-videos' && i + 1 < args.length) {
            maxVideos = parseInt(args[i + 1]);
            i++;
        } else if (arg === '--output' && i + 1 < args.length) {
            options.outputDir = args[i + 1];
            i++;
        } else if (arg === '--no-cache') {
            options.useCache = false;
        } else if (arg === '--help') {
            console.log(`
Pornhub Video Indexer

Usage:
  node pornhub-indexer.js --url "https://pornhub.com/view_video.php?viewkey=..."
  node pornhub-indexer.js --user "username" --max-videos 100
  node pornhub-indexer.js --channel "https://pornhub.com/channels/channelname"
  node pornhub-indexer.js --channel "https://pornhub.com/model/modelname"
  node pornhub-indexer.js --channel "https://pornhub.com/pornstar/pornstarname"
  
Options:
  --url URL           Extract metadata from a single video URL
  --user USERNAME     Extract all videos from a user profile (by username)
  --channel URL       Extract all videos from a channel/model/pornstar URL
  --max-videos N      Limit number of videos to process (default: all)
  --output DIR        Output directory (default: pornhub_data)
  --no-cache          Disable caching
  --help              Show this help message

Supported URL types:
  • Single videos:    /view_video.php?viewkey=...
  • User profiles:    /users/username
  • Channels:         /channels/channelname
  • Models:           /model/modelname  
  • Pornstars:        /pornstar/pornstarname
  • Playlists:        /playlist/...

Examples:
  node pornhub-indexer.js --url "https://pornhub.com/view_video.php?viewkey=abc123"
  node pornhub-indexer.js --channel "https://pornhub.com/channels/example" --max-videos 50
  node pornhub-indexer.js --channel "https://pornhub.com/model/examplemodel"
`);
            process.exit(0);
        }
    }

    if (!url && !username && !channelUrl) {
        console.error('❌ Please provide either --url, --user, or --channel option');
        console.error('Use --help for usage information');
        process.exit(1);
    }

    async function main() {
        const indexer = new PornhubIndexer(options);

        try {
            let metadata = [];
            let sourceIdentifier = '';

            if (url) {
                console.log('🚀 Processing URL...');
                metadata = await indexer.extractFromUrl(url, maxVideos);
                sourceIdentifier = indexer.detectUrlType(url);
            } else if (username) {
                console.log(`🚀 Extracting user videos for: ${username}`);
                metadata = await indexer.extractUserVideos(username, maxVideos);
                sourceIdentifier = `user_${username}`;
            } else if (channelUrl) {
                console.log(`🚀 Extracting from channel: ${channelUrl}`);
                metadata = await indexer.extractFromUrl(channelUrl, maxVideos);
                
                // Extract identifier from URL for filename
                const urlParts = channelUrl.split('/');
                const lastPart = urlParts[urlParts.length - 1] || urlParts[urlParts.length - 2];
                sourceIdentifier = `channel_${lastPart}`;
            }

            if (metadata.length > 0) {
                // Save data
                const timestamp = new Date().toISOString().replace(/[:.]/g, '-').split('T')[0];
                const filename = `pornhub_${sourceIdentifier}_${timestamp}.json`;
                
                await indexer.saveToJson(metadata, filename);

                // Generate and save summary
                const summary = indexer.generateSummary(metadata);
                if (summary) {
                    const summaryFilename = filename.replace('.json', '_summary.json');
                    await indexer.saveToJson([summary], summaryFilename);
                    indexer.printSummary(summary);
                }

                console.log(`\n🎉 Extraction complete! Found ${metadata.length} videos.`);
                console.log(`📁 Data saved to: ${options.outputDir}/${filename}`);
            } else {
                console.log('⚠️  No metadata extracted');
            }

        } catch (error) {
            console.error('❌ Extraction failed:', error.message);
            console.error('Stack trace:', error.stack);
            process.exit(1);
        }
    }

    main();
}