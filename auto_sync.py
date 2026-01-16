import os
import shutil
import subprocess
import datetime
import time

ROOT_DIR = r"D:\VsCode"
BACKUP_ROOT = os.path.join(ROOT_DIR, "_GIT_BACKUPS")

def safe_run_command(command, cwd):
    print(f"Running: {command}")
    try:
        subprocess.run(command, cwd=cwd, check=True, shell=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e}")
        return False

def neutralize_git_repos():
    print("--- 1. Neutralizing nested git repositories ---")
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
                    # If you want to update the backup, you'd need more complex logic here.
                    # For now, safety first: don't overwrite backups.
                    continue
                    
                try:
                    # Rename/Move
                    shutil.move(git_dir, backup_dest_git)
                    print(f"  -> Moved .git to {backup_dest_git}")
                except Exception as e:
                    print(f"  -> FAILED to move {git_dir}: {e}")

def sync_monorepo():
    print("\n--- 2. Syncing Monorepo to GitHub ---")
    
    # 1. Add all changes
    print("Staging changes...")
    safe_run_command("git add .", ROOT_DIR)
    
    # 2. Commit
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    commit_msg = f"Auto-sync: {timestamp}"
    print(f"Committing with message: '{commit_msg}'...")
    safe_run_command(f'git commit -m "{commit_msg}"', ROOT_DIR)
    
    # 3. Push
    print("Pushing to GitHub...")
    success = safe_run_command("git push origin master", ROOT_DIR)
    
    if success:
        print("\n✅ Sync completed successfully!")
    else:
        print("\n❌ Sync failed during push.")

if __name__ == "__main__":
    try:
        neutralize_git_repos()
        sync_monorepo()
    except Exception as e:
        print(f"\nCRITICAL ERROR: {e}")
    
    print("\nClosing in 5 seconds...")
    time.sleep(5)
