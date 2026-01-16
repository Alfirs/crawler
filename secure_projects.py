import os
import subprocess

ROOT_DIR = r"D:\VsCode"
ENV_FILE = ".env"
GITIGNORE = ".gitignore"

def safe_run_command(command, cwd):
    try:
        subprocess.run(command, cwd=cwd, check=True, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except subprocess.CalledProcessError:
        return False

def secure_project(project_path):
    print(f"Checking {project_path}...")
    
    # 1. Ensure .env is in .gitignore
    gitignore_path = os.path.join(project_path, GITIGNORE)
    env_ignored = False
    
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r", encoding="utf-8") as f:
            if any(ENV_FILE in line for line in f.readlines()):
                env_ignored = True
    
    if not env_ignored:
        print(f"  -> Adding .env to .gitignore")
        with open(gitignore_path, "a", encoding="utf-8") as f:
            f.write(f"\n{ENV_FILE}\n")
    else:
        print(f"  -> .env already ignored")

    # 2. Start git if not present (to be safe for step 3)
    if not os.path.exists(os.path.join(project_path, ".git")):
        print(f"  -> Initializing git repo")
        safe_run_command("git init", project_path)

    # 3. Remove .env from git cache if it was tracked
    env_path = os.path.join(project_path, ENV_FILE)
    if os.path.exists(env_path):
        # We try to remove it from the index. 
        # If it wasn't tracked, this command fails silently (which is fine).
        # We use --cached to keep the local file.
        success = safe_run_command(f"git rm --cached {ENV_FILE}", project_path)
        if success:
            print(f"  -> Removed .env from git cache")

def main():
    if not os.path.exists(ROOT_DIR):
        print(f"Directory {ROOT_DIR} does not exist.")
        return

    items = os.listdir(ROOT_DIR)
    for item in items:
        full_path = os.path.join(ROOT_DIR, item)
        if os.path.isdir(full_path) and not item.startswith("."):
            secure_project(full_path)

    print("\nDone! All projects secured.")

if __name__ == "__main__":
    main()
