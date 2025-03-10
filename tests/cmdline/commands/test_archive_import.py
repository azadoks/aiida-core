# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Tests for `verdi import`."""
from click.exceptions import BadParameter
from click.testing import CliRunner
import pytest

from aiida.cmdline.commands import cmd_archive
from aiida.orm import Group
from aiida.tools.archive import ArchiveFormatSqlZip
from tests.utils.archives import get_archive_file


class TestVerdiImport:
    """Tests for `verdi import`."""

    @pytest.fixture(autouse=True)
    def init_cls(self, clear_database_before_test):  # pylint: disable=unused-argument
        """Setup for each method"""
        # pylint: disable=attribute-defined-outside-init
        self.cli_runner = CliRunner()
        # Helper variables
        self.url_path = 'https://raw.githubusercontent.com/aiidateam/aiida-core/' \
            '0599dabf0887bee172a04f308307e99e3c3f3ff2/aiida/backends/tests/fixtures/export/migrate/'
        self.archive_path = 'export/migrate'
        self.newest_archive = f'export_v{ArchiveFormatSqlZip().latest_version}_simple.aiida'

    def test_import_no_archives(self):
        """Test that passing no valid archives will lead to command failure."""
        options = []
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)

        assert result.exception is not None, result.output
        assert 'Critical' in result.output
        assert result.exit_code != 0, result.output

    def test_import_non_existing_archives(self):
        """Test that passing a non-existing archive will lead to command failure."""
        options = ['non-existing-archive.aiida']
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)

        assert result.exception is not None, result.output
        assert result.exit_code != 0, result.output

    def test_import_archive(self):
        """
        Test import for archive files from disk
        """
        archives = [
            get_archive_file('arithmetic.add.aiida', filepath='calcjob'),
            get_archive_file(self.newest_archive, filepath=self.archive_path)
        ]

        options = [] + archives
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)

        assert result.exception is None, result.output
        assert result.exit_code == 0, result.output

    def test_import_to_group(self):
        """
        Test import to existing Group and that Nodes are added correctly for multiple imports of the same,
        as well as separate, archives.
        """
        archives = [
            get_archive_file('arithmetic.add.aiida', filepath='calcjob'),
            get_archive_file(self.newest_archive, filepath=self.archive_path)
        ]

        group_label = 'import_madness'
        group = Group(group_label).store()

        assert group.is_empty, 'The Group should be empty.'

        # Invoke `verdi import`, making sure there are no exceptions
        options = ['-G', group.label] + [archives[0]]
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)
        assert result.exception is None, result.output
        assert result.exit_code == 0, result.output

        assert not group.is_empty, 'The Group should no longer be empty.'

        nodes_in_group = group.count()

        # Invoke `verdi import` again, making sure Group count doesn't change
        options = ['-G', group.label] + [archives[0]]
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)
        assert result.exception is None, result.output
        assert result.exit_code == 0, result.output

        assert group.count() == \
            nodes_in_group, \
            f'The Group count should not have changed from {nodes_in_group}. Instead it is now {group.count()}'

        # Invoke `verdi import` again with new archive, making sure Group count is upped
        options = ['-G', group.label] + [archives[1]]
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)
        assert result.exception is None, result.output
        assert result.exit_code == 0, result.output

        assert group.count() > \
            nodes_in_group, \
            'There should now be more than {} nodes in group {} , instead there are {}'.format(
                nodes_in_group, group_label, group.count()
            )

    def test_import_make_new_group(self):
        """Make sure imported entities are saved in new Group"""
        # Initialization
        group_label = 'new_group_for_verdi_import'
        archives = [get_archive_file(self.newest_archive, filepath=self.archive_path)]

        # Check Group does not already exist
        group_search = Group.objects.find(filters={'label': group_label})
        assert len(group_search) == 0, f"A Group with label '{group_label}' already exists, this shouldn't be."

        # Invoke `verdi import`, making sure there are no exceptions
        options = ['-G', group_label] + archives
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)
        assert result.exception is None, result.output
        assert result.exit_code == 0, result.output

        # Make sure new Group was created
        (group, new_group) = Group.objects.get_or_create(group_label)
        assert not new_group, 'The Group should not have been created now, but instead when it was imported.'
        assert not group.is_empty, 'The Group should not be empty.'

    def test_no_import_group(self):
        """Test '--import-group/--no-import-group' options."""
        archives = [get_archive_file(self.newest_archive, filepath=self.archive_path)]

        assert Group.objects.count() == 0, 'There should be no Groups.'

        # Invoke `verdi import`
        options = archives
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)
        assert result.exception is None, result.output
        assert result.exit_code == 0, result.output

        assert Group.objects.count() == 5

        # Invoke `verdi import` again, creating another import group
        options = ['--import-group'] + archives
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)
        assert result.exception is None, result.output
        assert result.exit_code == 0, result.output

        assert Group.objects.count() == 6

        # Invoke `verdi import` again, but with no import group created
        options = ['--no-import-group'] + archives
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)
        assert result.exception is None, result.output
        assert result.exit_code == 0, result.output

        assert Group.objects.count() == 6

    @pytest.mark.skip('Due to summary being logged, this can not be checked against `results.output`.')  # pylint: disable=not-callable
    def test_comment_mode(self):
        """Test toggling comment mode flag"""
        archives = [get_archive_file(self.newest_archive, filepath=self.archive_path)]
        for mode in ['leave', 'newest', 'overwrite']:
            options = ['--comment-mode', mode] + archives
            result = self.cli_runner.invoke(cmd_archive.import_archive, options)
            assert result.exception is None, result.output
            assert result.exit_code == 0, result.output

    def test_import_old_local_archives(self):
        """ Test import of old local archives
        Expected behavior: Automatically migrate to newest version and import correctly.
        """
        for version in ArchiveFormatSqlZip().versions:
            archive, version = (f'export_v{version}_simple.aiida', f'{version}')
            options = [get_archive_file(archive, filepath=self.archive_path)]
            result = self.cli_runner.invoke(cmd_archive.import_archive, options)

            assert result.exception is None, result.output
            assert result.exit_code == 0, result.output
            assert version in result.output, result.exception
            assert f'Success: imported archive {options[0]}' in result.output, result.exception

    def test_import_old_url_archives(self):
        """ Test import of old URL archives
        Expected behavior: Automatically migrate to newest version and import correctly.
        """
        archive = 'export_v0.4_no_UPF.aiida'
        version = '0.4'

        options = [self.url_path + archive]
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)

        assert result.exception is None, result.output
        assert result.exit_code == 0, result.output
        assert version in result.output, result.exception
        assert f'Success: imported archive {options[0]}' in result.output, result.exception

    def test_import_url_and_local_archives(self):
        """Test import of both a remote and local archive"""
        url_archive = 'export_v0.4_no_UPF.aiida'
        local_archive = self.newest_archive

        options = [
            get_archive_file(local_archive, filepath=self.archive_path), self.url_path + url_archive,
            get_archive_file(local_archive, filepath=self.archive_path)
        ]
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)

        assert result.exception is None, result.output
        assert result.exit_code == 0, result.output

    def test_import_url_timeout(self):  # pylint: disable=no-self-use
        """Test a timeout to valid URL is correctly errored"""
        from aiida.cmdline.params.types import PathOrUrl

        timeout_url = 'http://www.google.com:81'

        test_timeout_path = PathOrUrl(exists=True, readable=True, timeout_seconds=0)
        with pytest.raises(BadParameter, match=f'ath "{timeout_url}" could not be reached within 0 s.'):
            test_timeout_path(timeout_url)

    def test_raise_malformed_url(self):
        """Test the correct error is raised when supplying a malformed URL"""
        malformed_url = 'htp://www.aiida.net'

        result = self.cli_runner.invoke(cmd_archive.import_archive, [malformed_url])

        assert result.exception is not None, result.output
        assert result.exit_code != 0, result.output

        error_message = 'could not be reached within'
        assert error_message in result.output, result.exception

    def test_migration(self):
        """Test options `--migration`/`--no-migration`

        `migration` = True (default), Expected: No query, migrate
        `migration` = False, Expected: No query, no migrate
        """
        archive = get_archive_file('export_v0.4_simple.aiida', filepath=self.archive_path)
        success_message = f'Success: imported archive {archive}'

        # Import "normally", but explicitly specifying `--migration`, make sure confirm message is present
        # `migration` = True (default), `non_interactive` = False (default), Expected: Query user, migrate
        options = ['--migration', archive]
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)

        assert result.exception is None, result.output
        assert result.exit_code == 0, result.output

        assert 'trying migration' in result.output, result.exception
        assert success_message in result.output, result.exception

        # Import using `--no-migration`, make sure confirm message has gone
        # `migration` = False, `non_interactive` = False (default), Expected: No query, no migrate
        options = ['--no-migration', archive]
        result = self.cli_runner.invoke(cmd_archive.import_archive, options)

        assert result.exception is not None, result.output
        assert result.exit_code != 0, result.output

        assert 'trying migration' not in result.output, result.exception
        assert success_message not in result.output, result.exception
