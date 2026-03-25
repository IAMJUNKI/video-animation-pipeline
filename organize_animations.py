import os
import csv
import shutil
import re

# 1. Configuration
BASE_DIR = "./Assets/Animations"
CSV_PATH = os.path.join(BASE_DIR, "metadata.csv")
# This is where the organized files will go
OUTPUT_DIR = os.path.join(BASE_DIR, "Library")

# 2. Category Mapping (Keywords found in your CSV)
# This helps the LLM find the right animation type
CATEGORIES = {
    'WALK': ['walk', 'stride', 'step', 'march', 'limp', 'stumble', 'stealthily'],
    'RUN': ['run', 'jog', 'sprint', 'scramble'],
    'JUMP': ['jump', 'leap', 'hop', 'flip', 'cartwheel'],
    'TALK_GESTURE': ['talk', 'explain', 'gesture', 'point', 'wave', 'shrug', 'laugh', 'story', 'directions'],
    'SIT_STAND': ['sit', 'stand', 'chair', 'stool', 'get up', 'lay down', 'crouch'],
    'DANCE': ['dance', 'salsa', 'ballet', 'pirouette', 'charleston', 'twist'],
    'SPORTS': ['basketball', 'soccer', 'kick', 'punch', 'boxing', 'golf', 'baseball', 'kick'],
    'DAILY_LIFE': ['drink', 'wash', 'clean', 'sweep', 'mop', 'phone', 'typing', 'eat', 'pick up'],
    'ANIMAL': ['monkey', 'bear', 'cat', 'dog', 'chicken', 'dinosaur', 'snake', 'elephant', 'penguin'],
}

def clean_text(text):
    """Removes special characters to make safe filenames."""
    text = text.lower().replace('"', '').replace("'", "")
    return re.sub(r'[^a-z0-9_]+', '_', text).strip('_')

def get_category(description):
    """Assigns a category based on keywords in the description."""
    desc_lower = description.lower()
    for cat, keywords in CATEGORIES.items():
        if any(key in desc_lower for key in keywords):
            return cat
    return "MISC"

def organize():
    if not os.path.exists(CSV_PATH):
        print(f"❌ Error: {CSV_PATH} not found. Run your download script first!")
        return

    # Create Library folder
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    print("📂 Starting organization of animations...")
    
    with open(CSV_PATH, mode='r', encoding='utf-8') as f:
        # We skip the first line because of the non-standard metadata header
        next(f) 
        reader = csv.reader(f)
        
        count = 0
        for row in reader:
            if len(row) < 2: continue
            
            file_name = row[0].strip()
            description = row[1].strip()
            
            # Find the file (it might be in subfolders like 01/01_01.fbx)
            found_path = None
            for root, dirs, files in os.walk(BASE_DIR):
                if file_name in files:
                    found_path = os.path.join(root, file_name)
                    break
            
            if found_path:
                category = get_category(description)
                safe_desc = clean_text(description)[:50] # Limit length
                
                # New Name: e.g., Library/WALK/02_01_walk_forward.fbx
                new_folder = os.path.join(OUTPUT_DIR, category)
                new_filename = f"{file_name.replace('.fbx', '')}_{safe_desc}.fbx"
                dest_path = os.path.join(new_folder, new_filename)
                
                os.makedirs(new_folder, exist_ok=True)
                shutil.copy2(found_path, dest_path) # Copy instead of move to be safe
                count += 1
            else:
                # Some files in the CSV might not exist in the repo
                pass

    print(f"✅ Success! Organized {count} animations into {OUTPUT_DIR}")
    print("🤖 Your LLM Director can now browse folders like 'WALK' and 'TALK_GESTURE'.")

if __name__ == "__main__":
    organize()