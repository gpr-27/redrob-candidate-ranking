#!/usr/bin/env python3
"""
Helper script to upload the project to Hugging Face Spaces.
This ensures the scoring/ folder and all required files are uploaded correctly.
"""

import sys
import os

try:
    from huggingface_hub import HfApi
except ImportError:
    print("Installing required library 'huggingface_hub'...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "huggingface_hub"])
    from huggingface_hub import HfApi

def main():
    print("=== Hugging Face Space Uploader ===")
    print("This script will upload your local files (including the scoring/ folder) to your Space.")
    print("You will need a Hugging Face Access Token with WRITE permission.")
    print("Get one here: https://huggingface.co/settings/tokens\n")

    token = input("Enter your Hugging Face Access Token: ").strip()
    if not token:
        print("Error: Token is required.")
        sys.exit(1)

    api = HfApi(token=token)
    repo_id = "praneethg27/redrob-ranker"

    print(f"\nUploading workspace to Space '{repo_id}'...")
    
    # We ignore large dataset files, word docs, and local caches
    ignore = [
        "candidates.jsonl",
        "candidates.jsonl.gz",
        "*.docx",
        "build_deck.py",
        "Redrob_Idea_Submission_Praneeth.pptx",
        ".git",
        "__pycache__",
        "*.pyc",
        ".DS_Store",
        ".venv",
        "venv"
    ]

    try:
        api.upload_folder(
            folder_path=".",
            repo_id=repo_id,
            repo_type="space",
            ignore_patterns=ignore
        )
        print("\n🚀 SUCCESS! All files uploaded successfully.")
        print("Hugging Face is rebuilding your Space as a native Streamlit app.")
        print("Check the build status here: https://huggingface.co/spaces/praneethg27/redrob-ranker")
    except Exception as e:
        print(f"\n❌ Error uploading: {e}")
        print("Make sure your token has 'WRITE' permission and the Space name is correct.")

if __name__ == "__main__":
    main()
