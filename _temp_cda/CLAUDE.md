Remember to run ruff on all new code and fix errors. Fix them properly instead of suppressing. Example:

    uv run ruff check <file>

When refactoring larger functions into shorter ones, place helper functions under the public function in a chronological order as if telling a story.
