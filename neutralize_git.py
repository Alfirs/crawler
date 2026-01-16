import os
import shutil
import time

ROOT_DIR = r"D:\VsCode"
BACKUP_ROOT = os.path.join(ROOT_DIR, "_GIT_BACKUPS")

def neutralize_git_repos():
    if not os.path.exists(BACKUP_ROOT):
        os.makedirs(BACKUP_ROOT)
        print(f"Created backup directory: {BACKUP_ROOT}")

    items = os.listdir(ROOT_DIR)
    
    for item in items:
        # Skip the backup dir itself and the root .git
        if item == "_GIT_BACKUPS" or item == ".git":
            continue
            
        full_path = os.path.join(ROOT_DIR, item)
        
        if os.path.isdir(full_path):
            git_dir = os.path.join(full_path, ".git")
            
            if os.path.exists(git_dir):
                print(f"Found nested git repo: {item}")
                
                # Create backup destination
                backup_dest_parent = os.path.join(BACKUP_ROOT, item)
                if not os.path.exists(backup_dest_parent):
                    os.makedirs(backup_dest_parent)
                
                backup_dest_git = os.path.join(backup_dest_parent, ".git")
                
                # Check if backup already exists
                if os.path.exists(backup_dest_git):
                    print(f"  WARNING: Backup already exists for {item}. Skipping to avoid overwrite.")
                    continue
                    
                try:
                    # Rename/Move
                    shutil.move(git_dir, backup_dest_git)
                    print(f"  -> Moved .git to {backup_dest_git}")
                except Exception as e:
                    print(f"  -> FAILED to move {git_dir}: {e}")

if __name__ == "__main__":
    neutralize_git_repos()
