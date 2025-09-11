import subprocess
import unittest.mock
import pytest

import hostinfo


def test_check_service_enabled_properly():
    """Test that check_service_enabled_properly correctly identifies services that will start on boot."""
    
    # Mock systemctl is-enabled --full output for a properly enabled service
    mock_output_enabled = """enabled
  /etc/systemd/system/test-service.service
  /etc/systemd/system/multi-user.target.wants/test-service.service
"""
    
    # Mock systemctl is-enabled --full output for a service that has symlink but won't start on boot
    mock_output_not_really_enabled = """enabled
  /etc/systemd/system/test-service.service
"""
    
    with unittest.mock.patch('subprocess.run') as mock_run:
        # Test case 1: Service that will actually start on boot
        mock_run.return_value = unittest.mock.Mock(
            returncode=0,
            stdout=mock_output_enabled,
            stderr=""
        )
        
        result = hostinfo.check_service_enabled_properly('test-service')
        assert result is True
        
        # Verify the correct command was called
        mock_run.assert_called_with(
            ['systemctl', 'is-enabled', '--full', 'test-service.service'],
            capture_output=True,
            text=True
        )
        
        # Test case 2: Service that appears enabled but won't start on boot
        mock_run.return_value = unittest.mock.Mock(
            returncode=0,
            stdout=mock_output_not_really_enabled,
            stderr=""
        )
        
        result = hostinfo.check_service_enabled_properly('test-service')
        assert result is False
        
        # Test case 3: Service that is not enabled at all
        mock_run.return_value = unittest.mock.Mock(
            returncode=1,
            stdout="disabled",
            stderr=""
        )
        
        result = hostinfo.check_service_enabled_properly('test-service')
        assert result is False


def test_get_all_running_services_uses_proper_enabled_check():
    """Test that get_all_running_services uses the proper enabled check."""
    
    # Mock the systemctl show output
    mock_show_output = """Id=test-service.service
ActiveState=active
UnitFileState=enabled

"""
    
    with unittest.mock.patch('subprocess.run') as mock_run:
        # Mock systemctl show
        def side_effect(*args, **kwargs):
            if args[0][0:2] == ['systemctl', 'show']:
                return unittest.mock.Mock(
                    returncode=0,
                    stdout=mock_show_output
                )
            # Mock systemctl is-enabled --full 
            elif args[0][0:3] == ['systemctl', 'is-enabled', '--full']:
                return unittest.mock.Mock(
                    returncode=0,
                    stdout="enabled\n  /etc/systemd/system/test-service.service\n  /etc/systemd/system/multi-user.target.wants/test-service.service\n"
                )
            # Mock journalctl for error checking
            elif args[0][0] == 'journalctl':
                return unittest.mock.Mock(
                    returncode=0,
                    stdout="No errors found"
                )
            else:
                return unittest.mock.Mock(returncode=0, stdout="")
        
        mock_run.side_effect = side_effect
        
        # Mock check_journal_errors to return False (no errors)
        with unittest.mock.patch('hostinfo.check_journal_errors', return_value=False):
            services = hostinfo.get_all_running_services()
            
            # Verify that the service is properly marked as enabled
            assert 'test-service' in services
            service_info = services['test-service'][0]
            assert service_info['is_enabled'] is True