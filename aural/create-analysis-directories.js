#!/usr/bin/env node

const fs = require('fs');
const path = require('path');

/**
 * Creates structured analysis directories for storing different types of analyses
 */
class AnalysisDirectoryManager {
  constructor(basePath = 'analysis_storage') {
    this.basePath = basePath;
  }

  /**
   * Creates directory structure for storing analyses
   */
  createDirectoryStructure() {
    const structure = {
      'sonnet_reference': 'Gold standard analyses by Claude Sonnet',
      'llm_approved': 'LLM analyses that have been manually verified as correct',
      'llm_rejected': 'LLM analyses that were incorrect (for learning)',
      'experimental': 'Testing new prompts and approaches',
      'comparison_reports': 'Analysis comparison reports and metrics'
    };

    // Create base directory
    if (!fs.existsSync(this.basePath)) {
      fs.mkdirSync(this.basePath, { recursive: true });
      console.log(`✅ Created base directory: ${this.basePath}`);
    }

    // Create subdirectories
    Object.entries(structure).forEach(([dir, description]) => {
      const dirPath = path.join(this.basePath, dir);
      if (!fs.existsSync(dirPath)) {
        fs.mkdirSync(dirPath, { recursive: true });
        console.log(`✅ Created directory: ${dirPath}`);
        
        // Create README for each directory
        const readmePath = path.join(dirPath, 'README.md');
        const readmeContent = `# ${dir.replace('_', ' ').toUpperCase()}\n\n${description}\n\n## Structure\n\nEach analysis is stored in a directory named after the post ID:\n\n\`\`\`\n${dir}/\n├── 1m9aefh/                    # Post ID\n│   ├── analysis.json           # The analysis result\n│   ├── metadata.json           # Analysis metadata (model, date, etc.)\n│   ├── original_post.json      # Copy of original Reddit post data\n│   └── notes.md               # Human notes/corrections (optional)\n└── README.md                  # This file\n\`\`\`\n\n## Usage\n\nStore analyses here using the AnalysisStorage helper:\n\n\`\`\`javascript\nconst storage = new AnalysisStorage();\nstorage.saveAnalysis('${dir}', postId, analysisData, metadata);\n\`\`\`\n`;
        fs.writeFileSync(readmePath, readmeContent);
      }
    });

    console.log(`\\n📁 Analysis directory structure created in: ${this.basePath}`);
    return this.basePath;
  }

  /**
   * Creates a directory for a specific post analysis
   */
  createPostDirectory(category, postId) {
    const postDir = path.join(this.basePath, category, postId);
    if (!fs.existsSync(postDir)) {
      fs.mkdirSync(postDir, { recursive: true });
      console.log(`✅ Created post directory: ${postDir}`);
    }
    return postDir;
  }

  /**
   * Lists all stored analyses by category
   */
  listAnalyses() {
    const categories = ['sonnet_reference', 'llm_approved', 'llm_rejected', 'experimental', 'comparison_reports'];
    const result = {};

    categories.forEach(category => {
      const categoryPath = path.join(this.basePath, category);
      if (fs.existsSync(categoryPath)) {
        const posts = fs.readdirSync(categoryPath)
          .filter(item => {
            const itemPath = path.join(categoryPath, item);
            return fs.statSync(itemPath).isDirectory() && item !== '.' && item !== '..';
          });
        result[category] = posts;
      } else {
        result[category] = [];
      }
    });

    return result;
  }
}

/**
 * Simplified analysis storage - one directory per post ID
 */
class AnalysisStorage {
  constructor(basePath = 'analyses') {
    this.basePath = basePath;
    this.ensureBaseDirectory();
  }

  ensureBaseDirectory() {
    if (!fs.existsSync(this.basePath)) {
      fs.mkdirSync(this.basePath, { recursive: true });
      console.log(`✅ Created analyses directory: ${this.basePath}`);
    }
  }

  /**
   * Creates directory for a specific post
   */
  createPostDirectory(postId) {
    const postDir = path.join(this.basePath, postId);
    if (!fs.existsSync(postDir)) {
      fs.mkdirSync(postDir, { recursive: true });
      console.log(`✅ Created post directory: ${postDir}`);
    }
    return postDir;
  }

  /**
   * Saves LLM analysis
   */
  saveLLMAnalysis(postId, analysisData, metadata = {}, originalPost = null) {
    const postDir = this.createPostDirectory(postId);
    
    // Save LLM analysis with metadata embedded
    const analysisWithMeta = {
      ...analysisData,
      llm_metadata: {
        post_id: postId,
        saved_at: new Date().toISOString(),
        analyzer: 'local_llm',
        ...metadata
      }
    };
    
    const analysisPath = path.join(postDir, 'llm_analysis.json');
    fs.writeFileSync(analysisPath, JSON.stringify(analysisWithMeta, null, 2));
    
    // Save original post if provided
    if (originalPost) {
      const originalPath = path.join(postDir, 'original_post.json');
      fs.writeFileSync(originalPath, JSON.stringify(originalPost, null, 2));
    }
    
    console.log(`✅ Saved LLM analysis for ${postId}`);
    return postDir;
  }

  /**
   * Saves reference/accepted analysis
   */
  saveReferenceAnalysis(postId, analysisData, metadata = {}, notes = null) {
    const postDir = this.createPostDirectory(postId);
    
    // Save reference analysis with metadata embedded
    const analysisWithMeta = {
      ...analysisData,
      reference_metadata: {
        post_id: postId,
        saved_at: new Date().toISOString(),
        analyzer: 'reference',
        ...metadata
      }
    };
    
    const analysisPath = path.join(postDir, 'reference_analysis.json');
    fs.writeFileSync(analysisPath, JSON.stringify(analysisWithMeta, null, 2));
    
    // Save notes if provided
    if (notes) {
      const notesPath = path.join(postDir, 'notes.md');
      fs.writeFileSync(notesPath, notes);
    }
    
    console.log(`✅ Saved reference analysis for ${postId}`);
    return postDir;
  }

  /**
   * Legacy method for backwards compatibility
   */
  saveAnalysis(category, postId, analysisData, metadata = {}, originalPost = null, notes = null) {
    if (category === 'reference' || category === 'sonnet_reference') {
      return this.saveReferenceAnalysis(postId, analysisData, metadata, notes);
    } else {
      return this.saveLLMAnalysis(postId, analysisData, metadata, originalPost);
    }
  }

  /**
   * Loads analysis data for a post
   */
  loadPostData(postId) {
    const postDir = path.join(this.basePath, postId);
    if (!fs.existsSync(postDir)) {
      throw new Error(`Post analysis not found: ${postId}`);
    }

    const result = { post_id: postId };
    
    // Load original post
    const originalPath = path.join(postDir, 'original_post.json');
    if (fs.existsSync(originalPath)) {
      result.originalPost = JSON.parse(fs.readFileSync(originalPath, 'utf8'));
    }
    
    // Load LLM analysis
    const llmPath = path.join(postDir, 'llm_analysis.json');
    if (fs.existsSync(llmPath)) {
      result.llmAnalysis = JSON.parse(fs.readFileSync(llmPath, 'utf8'));
    }
    
    // Load reference analysis
    const refPath = path.join(postDir, 'reference_analysis.json');
    if (fs.existsSync(refPath)) {
      result.referenceAnalysis = JSON.parse(fs.readFileSync(refPath, 'utf8'));
    }
    
    // Load notes
    const notesPath = path.join(postDir, 'notes.md');
    if (fs.existsSync(notesPath)) {
      result.notes = fs.readFileSync(notesPath, 'utf8');
    }

    return result;
  }

  /**
   * Legacy method for backwards compatibility
   */
  loadAnalysis(category, postId) {
    const postData = this.loadPostData(postId);
    
    if (category === 'reference' || category === 'sonnet_reference') {
      return {
        analysis: postData.referenceAnalysis,
        originalPost: postData.originalPost,
        notes: postData.notes
      };
    } else {
      return {
        analysis: postData.llmAnalysis,
        originalPost: postData.originalPost,
        notes: postData.notes
      };
    }
  }

  /**
   * Creates a comparison report between two analyses
   */
  createComparisonReport(postId, referenceCategory, testCategory, reportName = null) {
    const reference = this.loadAnalysis(referenceCategory, postId);
    const test = this.loadAnalysis(testCategory, postId);
    
    const reportData = {
      post_id: postId,
      reference_category: referenceCategory,
      test_category: testCategory,
      reference_analysis: reference.analysis,
      test_analysis: test.analysis,
      comparison_date: new Date().toISOString(),
      accuracy_score: this.calculateAccuracy(reference.analysis, test.analysis)
    };

    const reportId = reportName || `${postId}_${referenceCategory}_vs_${testCategory}`;
    this.saveAnalysis('comparison_reports', reportId, reportData, {
      analyzer: 'comparison_tool',
      type: 'accuracy_comparison'
    });

    return reportData;
  }

  /**
   * Simple accuracy calculation
   */
  calculateAccuracy(reference, test) {
    const criticalFields = [
      'script.url',
      'script.author', 
      'script.fillType',
      'performers.count',
      'performers.primary'
    ];

    let matches = 0;
    const results = {};

    criticalFields.forEach(fieldPath => {
      const refValue = this.getNestedValue(reference, fieldPath);
      const testValue = this.getNestedValue(test, fieldPath);
      const match = JSON.stringify(refValue) === JSON.stringify(testValue);
      
      results[fieldPath] = {
        reference: refValue,
        test: testValue,
        match: match
      };

      if (match) matches++;
    });

    return {
      overall_score: (matches / criticalFields.length) * 100,
      field_scores: results,
      total_fields: criticalFields.length,
      correct_fields: matches
    };
  }

  /**
   * Helper to get nested object values
   */
  getNestedValue(obj, path) {
    return path.split('.').reduce((current, key) => current && current[key], obj);
  }
}

// CLI usage
async function main() {
  const args = process.argv.slice(2);
  const command = args[0];

  const storage = new AnalysisStorage();

  switch (command) {
    case 'init':
      storage.manager.createDirectoryStructure();
      console.log('\\n🎯 Analysis storage system initialized!');
      console.log('\\nNext steps:');
      console.log('1. Save reference analysis: node create-analysis-directories.js save-reference');
      console.log('2. Test LLM analysis: node analyze-reddit-post.js <post> --save-approved');
      console.log('3. Compare analyses: node create-analysis-directories.js compare <post_id>');
      break;

    case 'save-reference':
      // Save the wingwoman reference analysis
      const { createSonnetReferenceAnalysis } = require('./sonnet-reference-analysis.js');
      const referenceAnalysis = createSonnetReferenceAnalysis();
      
      // Load original post
      const originalPost = JSON.parse(fs.readFileSync('H:\\\\Git\\\\gwasi-extractor\\\\reddit_data\\\\alekirser\\\\1m9aefh_f4m-your-party-girl-wingwoman-takes-you-home-inste.json', 'utf8'));
      
      storage.saveAnalysis(
        'sonnet_reference',
        '1m9aefh',
        referenceAnalysis,
        {
          analyzer: 'claude-sonnet-4',
          type: 'manual_reference',
          post_type: 'script_fill'
        },
        originalPost,
        'Reference analysis for wingwoman post. Used as gold standard for comparison with LLM analyses.'
      );
      
      console.log('✅ Saved Sonnet reference analysis for wingwoman post');
      break;

    case 'list':
      const analyses = storage.manager.listAnalyses();
      console.log('\\n📊 STORED ANALYSES:');
      Object.entries(analyses).forEach(([category, posts]) => {
        console.log(`\\n${category.toUpperCase()}:`);
        if (posts.length === 0) {
          console.log('  (none)');
        } else {
          posts.forEach(post => console.log(`  - ${post}`));
        }
      });
      break;

    case 'compare':
      const postId = args[1];
      const testCategory = args[2] || 'llm_approved';
      if (!postId) {
        console.error('Usage: node create-analysis-directories.js compare <post_id> [test_category]');
        console.error('Categories: llm_approved, llm_rejected, experimental');
        process.exit(1);
      }
      
      try {
        const report = storage.createComparisonReport(postId, 'sonnet_reference', testCategory);
        console.log(`\\n📊 COMPARISON REPORT FOR ${postId}:`);
        console.log(`Reference: sonnet_reference`);
        console.log(`Test: ${testCategory}`);
        console.log(`Overall Accuracy: ${report.accuracy_score.overall_score.toFixed(1)}%`);
        console.log(`Correct Fields: ${report.accuracy_score.correct_fields}/${report.accuracy_score.total_fields}`);
        console.log('\\nField-by-field comparison:');
        Object.entries(report.accuracy_score.field_scores).forEach(([field, data]) => {
          const status = data.match ? '✅' : '❌';
          console.log(`  ${status} ${field}: ${JSON.stringify(data.test)} (ref: ${JSON.stringify(data.reference)})`);
        });
      } catch (error) {
        console.error(`Error creating comparison: ${error.message}`);
      }
      break;

    default:
      console.log(`
Usage: node create-analysis-directories.js <command>

Commands:
  init              Initialize the analysis storage directory structure
  save-reference    Save the Sonnet reference analysis for wingwoman post
  list              List all stored analyses by category
  compare <post_id> Compare reference vs approved analysis for a post

Examples:
  node create-analysis-directories.js init
  node create-analysis-directories.js save-reference
  node create-analysis-directories.js list
  node create-analysis-directories.js compare 1m9aefh
`);
  }
}

if (require.main === module) {
  main().catch(console.error);
}

module.exports = { AnalysisDirectoryManager, AnalysisStorage };