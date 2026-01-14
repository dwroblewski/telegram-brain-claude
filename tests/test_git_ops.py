"""Tests for git_ops.py - git operations."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import git_ops


class TestInboxPath:
    """Test inbox path uses config."""

    @patch('git_ops.config')
    @patch('git_ops.subprocess.run')
    def test_uses_config_inbox_folder(self, mock_run, mock_config):
        """Should use INBOX_FOLDER from config, not hardcoded."""
        mock_config.INBOX_FOLDER = "custom-inbox"
        mock_config.GIT_AUTO_PUSH = True
        mock_run.return_value = MagicMock(returncode=0)

        # Create temp dir structure
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_path = Path(tmpdir) / "custom-inbox"
            # Note: mkdir is now done inside save_and_push_note

            result = git_ops.save_and_push_note(
                repo_path=tmpdir,
                filename="test.md",
                content="test content",
                push=False
            )

            # File should be in custom-inbox, not 0-Inbox
            assert (inbox_path / "test.md").exists()
            assert not (Path(tmpdir) / "0-Inbox" / "test.md").exists()
            assert result["file_saved"] is True

    @patch('git_ops.config')
    @patch('git_ops.subprocess.run')
    def test_creates_inbox_if_missing(self, mock_run, mock_config):
        """Should auto-create inbox folder if it doesn't exist."""
        mock_config.INBOX_FOLDER = "new-inbox"
        mock_config.GIT_AUTO_PUSH = False
        mock_run.return_value = MagicMock(returncode=0)

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            inbox_path = Path(tmpdir) / "new-inbox"
            assert not inbox_path.exists()

            result = git_ops.save_and_push_note(
                repo_path=tmpdir,
                filename="test.md",
                content="test content",
                push=False
            )

            assert inbox_path.exists()
            assert result["file_saved"] is True


class TestReturnValues:
    """Test return value structure."""

    @patch('git_ops.config')
    @patch('git_ops.subprocess.run')
    def test_returns_file_saved_and_git_committed(self, mock_run, mock_config):
        """Should return file_saved and git_committed keys."""
        mock_config.INBOX_FOLDER = "0-Inbox"
        mock_config.GIT_AUTO_PUSH = False
        mock_run.return_value = MagicMock(returncode=0)

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = git_ops.save_and_push_note(
                repo_path=tmpdir,
                filename="test.md",
                content="test content",
                push=False
            )

            assert "file_saved" in result
            assert "git_committed" in result
            assert result["file_saved"] is True
            assert result["git_committed"] is True

    @patch('git_ops.config')
    @patch('git_ops.subprocess.run')
    def test_file_saved_true_when_git_fails(self, mock_run, mock_config):
        """file_saved should be True even if git commit fails."""
        mock_config.INBOX_FOLDER = "0-Inbox"
        mock_config.GIT_AUTO_PUSH = False

        # First call (git add) succeeds, second call (git commit) fails
        from subprocess import CalledProcessError
        mock_run.side_effect = [
            MagicMock(returncode=0),  # git add
            CalledProcessError(1, "git commit"),  # git commit fails
        ]

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = git_ops.save_and_push_note(
                repo_path=tmpdir,
                filename="test.md",
                content="test content",
                push=False
            )

            assert result["file_saved"] is True
            assert result["git_committed"] is False
            assert result["success"] is False
