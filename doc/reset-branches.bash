#!/bin/bash
# Reset branches for splintercat testing
# This script prepares the llvm-mos repository for a fresh test run

set -e

REPO_DIR="/home/jbyrd/git/llvm-mos"

echo "Resetting branches for splintercat testing..."

# Remove any stale git lock files
if [ -f "$REPO_DIR/.git/index.lock" ]; then
    echo "Removing stale git lock file..."
    rm -f "$REPO_DIR/.git/index.lock"
fi

# Navigate to repository
cd "$REPO_DIR"

# Delete stable-test branch if it exists
echo "Deleting stable-test branch if it exists..."
git branch -D stable-test 2>/dev/null || echo "  (branch didn't exist)"

# Create fresh stable-test from upstream/main
echo "Creating fresh stable-test branch from upstream/main..."
git checkout -B stable-test remotes/upstream/main

# Verify state
echo ""
echo "Branch status:"
git branch --list stable-test
echo ""
echo "Reset complete. Ready for testing."