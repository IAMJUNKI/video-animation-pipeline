import os
from huggingface_hub import snapshot_download

def download_library():
    # Define the local directory
    local_dir = "./Assets/Animations"
    
    print("🚀 Starting download of CMU FBX library (approx 2GB)...")
    print("This might take a while depending on your internet speed.")

    try:
        # download_dir = snapshot_download(...)
        # local_dir_use_symlinks=False is KEY so Blender can see the files.
        snapshot_download(
            repo_id="gbionics/cmu-fbx",
            repo_type="dataset",
            local_dir=local_dir,
            local_dir_use_symlinks=False
        )
        print(f"\n✅ Success! All files downloaded to {local_dir}")
        print("Now you can run: python organize_animations.py")
        
    except Exception as e:
        print(f"\n❌ Error downloading: {e}")

if __name__ == "__main__":
    # Create the folder if it doesn't exist
    os.makedirs("./Assets/Animations", exist_ok=True)
    download_library()