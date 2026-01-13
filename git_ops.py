"""Git operations for saving and pushing notes."""
import subprocess
from pathlib import Path
from typing import Dict, Any


def save_and_push_note(
    repo_path: str,
    filename: str,
    content: str,
    push: bool = True
) -> Dict[str, Any]:
    """
    Save note to 0-Inbox/, commit, and optionally push.

    Returns dict with 'success' and 'error' keys.
    """
    try:
        inbox_path = Path(repo_path) / "0-Inbox"
        file_path = inbox_path / filename

        # Write file
        file_path.write_text(content)

        # Git add
        subprocess.run(
            ["git", "add", str(file_path)],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

        # Git commit
        commit_msg = f"Telegram capture: {filename.replace(' Telegram Capture.md', '')}"
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=repo_path,
            check=True,
            capture_output=True
        )

        # Git push (optional)
        if push:
            result = subprocess.run(
                ["git", "push"],
                cwd=repo_path,
                capture_output=True,
                text=True
            )
            if result.returncode != 0:
                return {"success": False, "error": f"Push failed: {result.stderr}"}

        return {"success": True, "error": None}

    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}
    except Exception as e:
        return {"success": False, "error": str(e)}
