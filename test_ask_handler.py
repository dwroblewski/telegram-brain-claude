"""Tests for ask_handler.py - read-only enforcement."""
import pytest
from ask_handler import enforce_read_only, READ_ONLY_TOOLS, BLOCKED_PATTERNS
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny


@pytest.mark.asyncio
async def test_enforce_read_only_allows_read_tools():
    """Read, Grep, Glob, LS should be allowed."""
    for tool in READ_ONLY_TOOLS:
        result = await enforce_read_only(tool, {"file_path": "/some/path.md"}, None)
        assert isinstance(result, PermissionResultAllow)
        assert result.behavior == "allow"


@pytest.mark.asyncio
async def test_enforce_read_only_blocks_write_tools():
    """Write, Edit, Bash should be blocked."""
    blocked_tools = ["Write", "Edit", "Bash", "NotebookEdit", "TodoWrite"]
    for tool in blocked_tools:
        result = await enforce_read_only(tool, {}, None)
        assert isinstance(result, PermissionResultDeny)
        assert result.behavior == "deny"
        assert "not allowed" in result.message


@pytest.mark.asyncio
async def test_enforce_read_only_blocks_sensitive_files():
    """Should block access to .env, credentials, etc."""
    sensitive_paths = [
        "/home/user/.env",
        "/project/credentials.json",
        "/secrets/api_key.txt",
        "/repo/.git/config",
    ]
    for path in sensitive_paths:
        result = await enforce_read_only("Read", {"file_path": path}, None)
        assert isinstance(result, PermissionResultDeny)
        assert result.behavior == "deny"
        assert "sensitive" in result.message.lower()


@pytest.mark.asyncio
async def test_enforce_read_only_allows_normal_vault_files():
    """Should allow reading normal vault files."""
    safe_paths = [
        "/home/user/vault/index.md",
        "/home/user/vault/areas/research/note.md",
        "/home/user/vault/projects/sample-project/notes.md",
    ]
    for path in safe_paths:
        result = await enforce_read_only("Read", {"file_path": path}, None)
        assert isinstance(result, PermissionResultAllow)
        assert result.behavior == "allow"


@pytest.mark.asyncio
async def test_enforce_read_only_handles_path_param():
    """Should check 'path' param as well as 'file_path'."""
    # Glob uses 'path' not 'file_path'
    result = await enforce_read_only("Glob", {"path": "/safe/path", "pattern": "*.md"}, None)
    assert isinstance(result, PermissionResultAllow)
    assert result.behavior == "allow"

    result = await enforce_read_only("Glob", {"path": "/has/.env/in/path"}, None)
    assert isinstance(result, PermissionResultDeny)
    assert result.behavior == "deny"
