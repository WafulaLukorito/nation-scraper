import os
import json
from urllib.parse import urlparse

MARKDOWN_DIR = r"c:\Users\jones\CodeZone\nation-scraper\markdown"
SUCCESS_LOG = r"c:\Users\jones\CodeZone\nation-scraper\success_log.json"

def clean_slug(url):
    parsed = urlparse(url)
    slug = parsed.path.split('/')[-1]
    slug = "".join([c for c in slug if c.isalnum() or c in ['-', '_']]).strip()
    return f"{slug}.md"

def main():
    if not os.path.exists(MARKDOWN_DIR):
        print(f"Directory {MARKDOWN_DIR} does not exist.")
        return
        
    files = os.listdir(MARKDOWN_DIR)
    deleted_files = set()
    
    print("Scanning markdown files...")
    for f in files:
        if not f.endswith(".md"):
            continue
        path = os.path.join(MARKDOWN_DIR, f)
        try:
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read()
        except Exception as e:
            print(f"Error reading {f}: {e}")
            continue
            
        parts = content.split("---")
        body = "---".join(parts[1:]).strip() if len(parts) >= 2 else content.strip()
        body_len = len(body)
        
        # Threshold is 1600 characters
        if body_len < 1600:
            print(f"Deleting paywalled file: {f} (Body Length: {body_len})")
            try:
                os.remove(path)
                deleted_files.add(f)
            except Exception as e:
                print(f"Error deleting {f}: {e}")
                
    print(f"\nTotal paywalled files deleted: {len(deleted_files)}")
    
    # Update success log
    if os.path.exists(SUCCESS_LOG):
        try:
            with open(SUCCESS_LOG, 'r', encoding='utf-8') as f:
                success_data = json.load(f)
        except Exception as e:
            print(f"Error reading success log: {e}")
            success_data = []
            
        initial_count = len(success_data)
        
        # Keep entry only if the corresponding markdown file exists on disk
        updated_success_data = []
        for entry in success_data:
            url = entry.get("url")
            filename = clean_slug(url)
            filepath = os.path.join(MARKDOWN_DIR, filename)
            
            if os.path.exists(filepath):
                # Ensure the entry has both "url" and "link"
                entry["link"] = url
                updated_success_data.append(entry)
            else:
                print(f"Removing from success log (file missing/deleted): {url}")
                
        print(f"Success log entries: {initial_count} -> {len(updated_success_data)}")
        
        try:
            with open(SUCCESS_LOG, 'w', encoding='utf-8') as f:
                json.dump(updated_success_data, f, indent=2)
            print("Successfully updated success_log.json")
        except Exception as e:
            print(f"Error writing success log: {e}")

if __name__ == "__main__":
    main()
