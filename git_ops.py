"""Git operations for saving and pushing notes."""
import subprocess
from pathlib import Path
from typing import Dict, Any

import config


def save_and_push_note(
    repo_path: str,
    filename: str,
    content: str,
    push: bool = True
) -> Dict[str, Any]:
    """
    Save note to inbox folder, commit, and optionally push.

    Returns dict with 'success', 'error', 'file_saved', and 'git_committed' keys.
    """
    result = {"success": False, "error": None, "file_saved": False, "git_committed": False}

    try:
        inbox_path = Path(repo_path) / config.INBOX_FOLDER
        inbox_path.mkdir(parents=True, exist_ok=True)
        file_path = inbox_path / filename

        # Step 1: Write file
        file_path.write_text(content)
        result["file_saved"] = True

        # Step 2: Git add
        subprocess.run(
            ["git", "add", str(file_path)],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

        # Step 3: Git commit
        commit_msg = f"Telegram capture: {filename.replace(' Telegram Capture.md', '')}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=repo_path,
            check=True,
            capture_output=True
        )
        result["git_committed"] = True

        # Step 4: Git push (optional)
        if push and config.GIT_AUTO_PUSH:
            push_result = subprocess.run(
                ["git", "push"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            if push_result.returncode != 0:
                result["error"] = f"Push failed: {push_result.stderr}"
                return result

        result["success"] = True
        return result

    except subprocess.CalledProcessError as e:
        result["error"] = f"Git error: {e}"
        return result
    except Exception as e:
        result["error"] = str(e)
        return result
