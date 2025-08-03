# LLM REJECTED

LLM analyses that were incorrect (for learning)

## Structure

Each analysis is stored in a directory named after the post ID:

```
llm_rejected/
├── 1m9aefh/                    # Post ID
│   ├── analysis.json           # The analysis result
│   ├── metadata.json           # Analysis metadata (model, date, etc.)
│   ├── original_post.json      # Copy of original Reddit post data
│   └── notes.md               # Human notes/corrections (optional)
└── README.md                  # This file
```

## Usage

Store analyses here using the AnalysisStorage helper:

```javascript
const storage = new AnalysisStorage();
storage.saveAnalysis('llm_rejected', postId, analysisData, metadata);
```
