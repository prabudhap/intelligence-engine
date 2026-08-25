import os
import subprocess
import sys

def setup_git_hooks():
    print("🔧 Setting up Git pre-commit hook pipeline...")
    try:
        # Configure Git to use .githooks directory for hooks
        res = subprocess.run(["git", "config", "core.hooksPath", ".githooks"], capture_output=True, text=True)
        if res.returncode == 0:
            print("✅ Successfully configured Git hooks directory to '.githooks'.")
        else:
            print(f"⚠️ Failed to set git config core.hooksPath: {res.stderr}")
    except Exception as e:
        print(f"❌ Error setting up git hooks: {e}")

if __name__ == "__main__":
    setup_git_hooks()
