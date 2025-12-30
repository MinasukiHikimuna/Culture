/**
 * Reddit Resolver - Shared module for Reddit content resolution
 *
 * Handles:
 * - Fetching Reddit posts from JSON API
 * - Detecting and resolving crossposts
 * - Normalizing post data structure
 */

const USER_AGENT = 'GWASIExtractor/1.0 (audio archival tool)';

class RedditResolver {
  constructor(options = {}) {
    this.requestDelay = options.requestDelay || 1500; // 1.5 seconds between requests
    this.maxRetries = options.maxRetries || 1;
    this.lastRequestTime = 0;
  }

  /**
   * Resolve a Reddit post - handles crossposts, direct URLs, and existing data
   * @param {string|object} input - Reddit URL or post data object
   * @returns {object} Complete post data with selftext
   */
  async resolve(input) {
    // If input is a URL string, fetch from Reddit
    if (typeof input === 'string') {
      return await this.fetchRedditPost(input);
    }

    // If input is post data, check if it needs crosspost resolution
    if (this.isCrosspost(input)) {
      const targetUrl = this.extractCrosspostTarget(input);
      if (targetUrl) {
        console.log(`  🔗 Resolving crosspost: ${targetUrl}`);
        const resolved = await this.fetchRedditPost(targetUrl);
        if (resolved) {
          // Preserve original post metadata, add resolved content
          return {
            ...input,
            selftext: resolved.selftext,
            resolved_from: targetUrl,
            original_post: resolved
          };
        }
      }
      return null; // Could not resolve crosspost
    }

    // Check if crosspost_parent_list contains the data we need
    if (input.crosspost_parent_list && input.crosspost_parent_list.length > 0) {
      const parent = input.crosspost_parent_list[0];
      if (parent.selftext) {
        console.log(`  📋 Using crosspost_parent_list data`);
        return {
          ...input,
          selftext: parent.selftext,
          resolved_from: `crosspost_parent_list`,
          original_post: parent
        };
      }
    }

    // Return as-is if no resolution needed
    return input;
  }

  /**
   * Detect if a post is a crosspost that needs resolution
   */
  isCrosspost(postData) {
    // Check explicit crosspost indicators
    if (postData.is_self === false) {
      // Check if URL points to another Reddit post (including user profile posts)
      const url = postData.url || '';
      // Match /r/subreddit/comments/ or /r/u_username/comments/
      if ((url.includes('/r/') || url.includes('/u_')) && url.includes('/comments/')) {
        return true;
      }
    }

    // Check domain - crossposts often have domain "reddit.com" or "self.{username}"
    // where the post is actually on their user profile
    if (postData.domain === 'reddit.com') {
      return true;
    }

    // User profile crossposts: domain is "self.username" but is_self is false
    if (postData.is_self === false && postData.domain?.startsWith('self.')) {
      return true;
    }

    // Check if selftext is empty but we have crosspost indicators
    if (!postData.selftext?.trim() && postData.crosspost_parent_list?.length > 0) {
      return true;
    }

    return false;
  }

  /**
   * Extract the target URL from a crosspost
   */
  extractCrosspostTarget(postData) {
    const url = postData.url || '';

    // If URL is a Reddit post URL (including user profile posts), use it directly
    // Handles: /r/subreddit/comments/... and /r/u_username/comments/...
    if (url.includes('/comments/')) {
      // Normalize URL - ensure it's a full URL
      if (url.startsWith('/r/') || url.startsWith('/u/') || url.startsWith('/u_')) {
        return `https://www.reddit.com${url}`;
      }
      if (url.includes('reddit.com')) {
        return url;
      }
    }

    // Try to extract from crosspost_parent field
    if (postData.crosspost_parent) {
      // crosspost_parent is typically "t3_postid"
      const postId = postData.crosspost_parent.replace('t3_', '');
      // We don't know the subreddit, so we can't construct a full URL
      // But we can try using the parent list if available
    }

    return null;
  }

  /**
   * Extract post ID from Reddit URL
   */
  extractPostId(url) {
    // Handle various Reddit URL formats:
    // https://www.reddit.com/r/gonewildaudio/comments/xyz123/title/
    // https://reddit.com/r/gonewildaudio/comments/xyz123/
    // /r/gonewildaudio/comments/xyz123/
    const match = url.match(/\/comments\/([a-z0-9]+)/i);
    return match ? match[1] : null;
  }

  /**
   * Respect rate limiting
   */
  async waitForRateLimit() {
    const now = Date.now();
    const timeSinceLastRequest = now - this.lastRequestTime;
    if (timeSinceLastRequest < this.requestDelay) {
      const waitTime = this.requestDelay - timeSinceLastRequest;
      await new Promise(resolve => setTimeout(resolve, waitTime));
    }
    this.lastRequestTime = Date.now();
  }

  /**
   * Fetch Reddit post content from JSON API
   */
  async fetchRedditPost(url) {
    await this.waitForRateLimit();

    // Normalize URL to JSON endpoint
    let jsonUrl = url;

    // Remove trailing slash and add .json
    jsonUrl = jsonUrl.replace(/\/$/, '');
    if (!jsonUrl.endsWith('.json')) {
      jsonUrl = jsonUrl + '.json';
    }

    // Ensure it's a full URL
    if (jsonUrl.startsWith('/r/')) {
      jsonUrl = `https://www.reddit.com${jsonUrl}`;
    }

    let lastError = null;
    for (let attempt = 0; attempt <= this.maxRetries; attempt++) {
      try {
        if (attempt > 0) {
          console.log(`  ⏳ Retry attempt ${attempt}...`);
          await new Promise(resolve => setTimeout(resolve, 2000));
        }

        const response = await fetch(jsonUrl, {
          headers: {
            'User-Agent': USER_AGENT,
            'Accept': 'application/json'
          }
        });

        if (response.status === 404) {
          console.log(`  ⚠️  Post not found (404): ${url}`);
          return null;
        }

        if (response.status === 429) {
          console.log(`  ⚠️  Rate limited, waiting...`);
          await new Promise(resolve => setTimeout(resolve, 5000));
          continue;
        }

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const contentType = response.headers.get('content-type');
        if (!contentType?.includes('application/json')) {
          throw new Error(`Unexpected content type: ${contentType}`);
        }

        const data = await response.json();

        // Reddit API returns array: [post, comments]
        const post = data[0]?.data?.children?.[0]?.data;

        if (!post) {
          throw new Error('Could not find post data in response');
        }

        // Check if post was deleted or removed
        if (post.selftext === '[deleted]' || post.selftext === '[removed]') {
          console.log(`  ⚠️  Post was deleted/removed`);
          return null;
        }

        return {
          id: post.id,
          title: post.title,
          selftext: post.selftext || '',
          author: post.author,
          created_utc: post.created_utc,
          subreddit: post.subreddit,
          url: post.url,
          permalink: post.permalink,
          is_self: post.is_self,
          domain: post.domain,
          link_flair_text: post.link_flair_text,
          score: post.score,
          upvote_ratio: post.upvote_ratio,
          num_comments: post.num_comments,
          over_18: post.over_18,
          crosspost_parent_list: post.crosspost_parent_list
        };

      } catch (error) {
        lastError = error;
        console.log(`  ⚠️  Fetch error: ${error.message}`);
      }
    }

    console.log(`  ❌ Failed to fetch after ${this.maxRetries + 1} attempts`);
    return null;
  }

  /**
   * Normalize Reddit URL to standard format
   */
  normalizeUrl(url) {
    // Remove query parameters and fragments
    let normalized = url.split('?')[0].split('#')[0];

    // Ensure https://www.reddit.com prefix
    if (normalized.startsWith('/r/')) {
      normalized = `https://www.reddit.com${normalized}`;
    } else if (normalized.startsWith('reddit.com')) {
      normalized = `https://www.${normalized}`;
    } else if (normalized.startsWith('www.reddit.com')) {
      normalized = `https://${normalized}`;
    }

    // Remove trailing slash
    normalized = normalized.replace(/\/$/, '');

    return normalized;
  }
}

module.exports = { RedditResolver };
