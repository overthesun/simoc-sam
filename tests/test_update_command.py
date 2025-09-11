import subprocess
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Import the simoc-sam script as a module
import sys
import os
simoc_sam_dir = Path(__file__).parent.parent
sys.path.insert(0, str(simoc_sam_dir))

# Import the module by loading the script
import importlib.util
spec = importlib.util.spec_from_file_location("simoc_sam_script", simoc_sam_dir / "simoc-sam.py")
simoc_sam_script = importlib.util.module_from_spec(spec)
spec.loader.exec_module(simoc_sam_script)


def test_update_command_exists():
    """Test that the update command is registered."""
    assert 'update' in simoc_sam_script.COMMANDS
    assert simoc_sam_script.COMMANDS['update'] == simoc_sam_script.update


def test_update_command_clean_repo_wrong_branch():
    """Test update command when repo is clean but not on master branch."""
    with patch('subprocess.run') as mock_run:
        # Mock git status (clean repo)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=''),  # git status --porcelain
            MagicMock(returncode=0, stdout='feature-branch\n'),  # git rev-parse --abbrev-ref HEAD
        ]
        
        result = simoc_sam_script.update()
        
        assert result is False
        assert mock_run.call_count == 2
        # Check that git status was called
        mock_run.assert_any_call(['git', 'status', '--porcelain'], 
                                capture_output=True, text=True)
        # Check that branch check was called
        mock_run.assert_any_call(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], 
                                capture_output=True, text=True)


def test_update_command_dirty_repo():
    """Test update command when repo has uncommitted changes."""
    with patch('subprocess.run') as mock_run:
        # Mock git status (dirty repo)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=' M file.txt\n'),  # git status --porcelain
        ]
        
        result = simoc_sam_script.update()
        
        assert result is False
        assert mock_run.call_count == 1
        # Check that git status was called
        mock_run.assert_any_call(['git', 'status', '--porcelain'], 
                                capture_output=True, text=True)


def test_update_command_clean_repo_master_branch():
    """Test update command when repo is clean and on master branch."""
    with patch('subprocess.run') as mock_run, \
         patch.object(simoc_sam_script, 'run') as mock_run_helper:
        
        # Mock git status (clean repo) and branch check (master)
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=''),  # git status --porcelain
            MagicMock(returncode=0, stdout='master\n'),  # git rev-parse --abbrev-ref HEAD
        ]
        
        # Mock the run helper function
        mock_run_helper.return_value = True
        
        result = simoc_sam_script.update()
        
        assert result is True
        assert mock_run.call_count == 2
        # Check that git pull was called through run helper
        mock_run_helper.assert_called_once_with(['git', 'pull'])


def test_update_command_git_status_error():
    """Test update command when git status command fails."""
    with patch('subprocess.run') as mock_run:
        # Mock git status failure
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout=''),  # git status --porcelain fails
        ]
        
        result = simoc_sam_script.update()
        
        assert result is False
        assert mock_run.call_count == 1


def test_update_command_git_branch_error():
    """Test update command when git branch check command fails."""
    with patch('subprocess.run') as mock_run:
        # Mock git status success but branch check failure
        mock_run.side_effect = [
            MagicMock(returncode=0, stdout=''),  # git status --porcelain
            MagicMock(returncode=1, stdout=''),  # git rev-parse --abbrev-ref HEAD fails
        ]
        
        result = simoc_sam_script.update()
        
        assert result is False
        assert mock_run.call_count == 2