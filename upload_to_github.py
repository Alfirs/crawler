import os
import subprocess
import time

ROOT_DIR = r"D:\VsCode"
GH_PATH = r"C:\Program Files\GitHub CLI\gh.exe"

def safe_run_command(command, cwd):
    try:
        # Capture output to check for errors/success
        result = subprocess.run(command, cwd=cwd, check=True, shell=True, capture_output=True, text=True)
        return True, result.stdout
    except subprocess.CalledProcessError as e:
        return False, e.stderr

def upload_project(project_path, folder_name):
    print(f"Processing {folder_name}...")
    
    # 1. Create Private Repo
    # --source=. uses the current directory
    # --private makes it private
    # --push attempts to push the current branch
    # command: gh repo create <name> --private --source=. --remote=origin --push
    
    # Check if remote exists
    has_remote, _ = safe_run_command("git remote show origin", project_path)
    
    if has_remote:
        print(f"  -> Repo likely already linked (remote origin exists). Skipping creation.")
        # Optional: try pushing anyway?
        return

    print(f"  -> Creating private repo on GitHub...")
    # usage: gh repo create [name] [flags]
    # We use the folder name as the repo name. 
    # NOTE: This might fail if the name is taken or invalid.
    cmd = f'"{GH_PATH}" repo create "{folder_name}" --private --source=. --remote=origin'
    
    success, output = safe_run_command(cmd, project_path)
    if success:
        print(f"  -> Repo created successfully.")
        # Push
        print(f"  -> Pushing code...")
        push_success, push_out = safe_run_command("git push -u origin main", project_path)
        if not push_success:
             # Try master if main fails?
             push_success, push_out = safe_run_command("git push -u origin master", project_path)
        
        if push_success:
            print("  -> Pushed successfully.")
        else:
            print(f"  -> Failed to push: {push_out.strip()}")
            
    else:
        print(f"  -> Failed to create repo: {output.strip()}")

def main():
    if not os.path.exists(ROOT_DIR):
        print(f"Directory {ROOT_DIR} does not exist.")
        return

    # Check auth status first
    success, _ = safe_run_command(f'"{GH_PATH}" auth status', ROOT_DIR)
    if not success:
        print("ERROR: You are not logged into GitHub. Please run 'gh auth login' first.")
        return

    items = os.listdir(ROOT_DIR)
    for item in items:
        full_path = os.path.join(ROOT_DIR, item)
        if os.path.isdir(full_path) and not item.startswith("."):
            upload_project(full_path, item)

    print("\nBatch upload process completed.")

if __name__ == "__main__":
    main()
