# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
# pylint: disable=unused-argument,redefined-outer-name
"""Tests for the 'verdi code' command."""
import os
import tempfile
import textwrap

import click
import pytest

from aiida.cmdline.commands import cmd_code
from aiida.cmdline.params.options.commands.code import validate_label_uniqueness
from aiida.common.exceptions import MultipleObjectsError, NotExistent
from aiida.orm import Code, Computer, load_code


@pytest.fixture
def code(aiida_localhost):
    """Return a ``Code`` instance."""
    code = Code(
        input_plugin_name='core.arithmetic.add',
        remote_computer_exec=[aiida_localhost, '/remote/abs/path'],
    )
    code.label = 'code'
    code.description = 'desc'
    code.set_prepend_text('text to prepend')
    code.set_append_text('text to append')
    code.store()

    return code


def test_help(run_cli_command):
    """Test the help message."""
    run_cli_command(cmd_code.setup_code, ['--help'])


@pytest.mark.usefixtures('clear_database_before_test')
def test_code_list_no_codes_error_message(run_cli_command):
    """Test ``verdi code list`` when no codes exist."""
    result = run_cli_command(cmd_code.code_list)
    assert '# No codes found matching the specified criteria.' in result.output


@pytest.mark.usefixtures('clear_database_before_test')
def test_code_list(run_cli_command, code):
    """Test ``verdi code list``."""
    code2 = Code(
        input_plugin_name='core.templatereplacer',
        remote_computer_exec=[code.computer, '/remote/abs/path'],
    )
    code2.label = 'code2'
    code2.store()

    options = ['-A', '-a', '-o', '--input-plugin=core.arithmetic.add', f'--computer={code.computer.label}']
    result = run_cli_command(cmd_code.code_list, options)
    assert str(code.pk) in result.output
    assert code2.label not in result.output
    assert code.computer.label in result.output
    assert '# No codes found matching the specified criteria.' not in result.output


@pytest.mark.usefixtures('clear_database_before_test')
def test_code_list_hide(run_cli_command, code):
    """Test that hidden codes are shown (or not) properly."""
    code.hide()
    options = ['-A']
    result = run_cli_command(cmd_code.code_list, options)
    assert code.full_label not in result.output

    options = ['-a']
    result = run_cli_command(cmd_code.code_list, options)
    assert code.full_label in result.output


@pytest.mark.usefixtures('clear_database_before_test')
def test_hide_one(run_cli_command, code):
    """Test ``verdi code hide``."""
    run_cli_command(cmd_code.hide, [str(code.pk)])
    assert code.hidden


@pytest.mark.usefixtures('clear_database_before_test')
def test_reveal_one(run_cli_command, code):
    """Test ``verdi code reveal``."""
    run_cli_command(cmd_code.reveal, [str(code.pk)])
    assert not code.hidden


@pytest.mark.usefixtures('clear_database_before_test')
def test_relabel_code(run_cli_command, code):
    """Test ``verdi code relabel``."""
    run_cli_command(cmd_code.relabel, [str(code.pk), 'new_code'])
    assert load_code(code.pk).label == 'new_code'


@pytest.mark.usefixtures('clear_database_before_test')
def test_relabel_code_full(run_cli_command, code):
    """Test ``verdi code relabel`` passing the full code label."""
    run_cli_command(cmd_code.relabel, [str(code.pk), f'new_code@{code.computer.label}'])
    assert load_code(code.pk).label == 'new_code'


@pytest.mark.usefixtures('clear_database_before_test')
def test_relabel_code_full_bad(run_cli_command, code):
    """Test ``verdi code relabel`` with an incorrect full code label."""
    run_cli_command(cmd_code.relabel, [str(code.pk), 'new_code@otherstuff'], raises=True)


@pytest.mark.usefixtures('clear_database_before_test')
def test_code_delete_one_force(run_cli_command, code):
    """Test force code deletion."""
    run_cli_command(cmd_code.delete, [str(code.pk), '--force'])

    with pytest.raises(NotExistent):
        load_code('code')


@pytest.mark.usefixtures('clear_database_before_test')
def test_code_show(run_cli_command, code):
    result = run_cli_command(cmd_code.show, [str(code.pk)])
    assert str(code.pk) in result.output


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_code_duplicate_non_interactive(run_cli_command, code, non_interactive_editor):
    """Test code duplication non-interactive."""
    label = 'code_duplicate_noninteractive'
    run_cli_command(cmd_code.code_duplicate, ['--non-interactive', f'--label={label}', str(code.pk)])

    duplicate = load_code(label)
    assert code.description == duplicate.description
    assert code.get_prepend_text() == duplicate.get_prepend_text()
    assert code.get_append_text() == duplicate.get_append_text()
    assert code.get_input_plugin_name() == duplicate.get_input_plugin_name()


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_noninteractive_remote(run_cli_command, aiida_localhost, non_interactive_editor):
    """Test non-interactive remote code setup."""
    label = 'noninteractive_remote'
    options = [
        '--non-interactive', f'--label={label}', '--description=description', '--input-plugin=core.arithmetic.add',
        '--on-computer', f'--computer={aiida_localhost.label}', '--remote-abs-path=/remote/abs/path'
    ]
    run_cli_command(cmd_code.setup_code, options)
    assert isinstance(load_code(label), Code)


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_noninteractive_upload(run_cli_command, non_interactive_editor):
    """Test non-interactive code setup."""
    label = 'noninteractive_upload'
    options = [
        '--non-interactive', f'--label={label}', '--description=description', '--input-plugin=core.arithmetic.add',
        '--store-in-db', f'--code-folder={os.path.dirname(__file__)}', f'--code-rel-path={os.path.basename(__file__)}'
    ]
    run_cli_command(cmd_code.setup_code, options)
    assert isinstance(load_code(label), Code)


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_interactive_remote(run_cli_command, aiida_localhost, non_interactive_editor):
    """Test interactive remote code setup."""
    label = 'interactive_remote'
    user_input = '\n'.join(['yes', aiida_localhost.label, label, 'desc', 'core.arithmetic.add', '/remote/abs/path'])
    run_cli_command(cmd_code.setup_code, user_input=user_input)
    assert isinstance(load_code(label), Code)


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_interactive_upload(run_cli_command, non_interactive_editor):
    """Test interactive code setup."""
    label = 'interactive_upload'
    dirname = os.path.dirname(__file__)
    basename = os.path.basename(__file__)
    user_input = '\n'.join(['no', label, 'description', 'core.arithmetic.add', dirname, basename])
    run_cli_command(cmd_code.setup_code, user_input=user_input)
    assert isinstance(load_code(label), Code)


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_mixed(run_cli_command, aiida_localhost, non_interactive_editor):
    """Test mixed (interactive/from config) code setup."""
    label = 'mixed_remote'
    options = ['--description=description', '--on-computer', '--remote-abs-path=/remote/abs/path']
    user_input = '\n'.join([aiida_localhost.label, label, 'core.arithmetic.add'])
    run_cli_command(cmd_code.setup_code, options, user_input=user_input)
    assert isinstance(load_code(label), Code)


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_code_duplicate_interactive(run_cli_command, aiida_local_code_factory, non_interactive_editor):
    """Test code duplication interactive."""
    label = 'code_duplicate_interactive'
    user_input = f'\n\n{label}\n\n\n\n'
    code = aiida_local_code_factory('core.arithmetic.add', '/bin/cat', label='code')
    run_cli_command(cmd_code.code_duplicate, [str(code.pk)], user_input=user_input)

    duplicate = load_code(label)
    assert code.description == duplicate.description
    assert code.get_prepend_text() == duplicate.get_prepend_text()
    assert code.get_append_text() == duplicate.get_append_text()


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_code_duplicate_ignore(run_cli_command, aiida_local_code_factory, non_interactive_editor):
    """Providing "!" to description should lead to empty description.

    Regression test for: https://github.com/aiidateam/aiida-core/issues/3770
    """
    label = 'code_duplicate_interactive'
    user_input = f'\n\n{label}\n!\n\n\n'
    code = aiida_local_code_factory('core.arithmetic.add', '/bin/cat', label='code')
    run_cli_command(cmd_code.code_duplicate, [str(code.pk)], user_input=user_input)

    duplicate = load_code(label)
    assert duplicate.description == ''


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_from_config_local_file(non_interactive_editor, run_cli_command, aiida_localhost):
    """Test setting up a code from a config file on disk."""
    config_file_template = textwrap.dedent(
        """
        label: {label}
        computer: {computer}
        input_plugin: core.arithmetic.add
        remote_abs_path: /remote/abs/path
        """
    )

    label = 'noninteractive_config'
    with tempfile.NamedTemporaryFile('w') as handle:
        handle.write(config_file_template.format(label=label, computer=aiida_localhost.label))
        handle.flush()
        run_cli_command(cmd_code.setup_code, ['--non-interactive', '--config', os.path.realpath(handle.name)])
        assert isinstance(load_code(label), Code)


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('non_interactive_editor', ('vim -cwq',), indirect=True)
def test_from_config_url(non_interactive_editor, run_cli_command, aiida_localhost, monkeypatch):
    """Test setting up a code from a config file from URL."""
    from urllib import request

    monkeypatch.setattr(
        request, 'urlopen',
        lambda *args, **kwargs: config_file_template.format(label=label, computer=aiida_localhost.label)
    )

    config_file_template = textwrap.dedent(
        """
        label: {label}
        computer: {computer}
        input_plugin: core.arithmetic.add
        remote_abs_path: /remote/abs/path
        """
    )

    label = 'noninteractive_config_url'
    fake_url = 'https://my.url.com'
    run_cli_command(cmd_code.setup_code, ['--non-interactive', '--config', fake_url])
    assert isinstance(load_code(label), Code)


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('non_interactive_editor', ('sleep 1; vim -cwq',), indirect=True)
def test_code_setup_remote_duplicate_full_label_interactive(
    run_cli_command, aiida_local_code_factory, aiida_localhost, non_interactive_editor
):
    """Test ``verdi code setup`` for a remote code in interactive mode specifying an existing full label."""
    label = 'some-label'
    aiida_local_code_factory('core.arithmetic.add', '/bin/cat', computer=aiida_localhost, label=label)
    assert isinstance(load_code(label), Code)

    label_unique = 'label-unique'
    user_input = '\n'.join(['yes', aiida_localhost.label, label, label_unique, 'd', 'core.arithmetic.add', '/bin/bash'])
    run_cli_command(cmd_code.setup_code, user_input=user_input)
    assert isinstance(load_code(label_unique), Code)


@pytest.mark.usefixtures('clear_database_before_test')
@pytest.mark.parametrize('label_first', (True, False))
def test_code_setup_remote_duplicate_full_label_non_interactive(
    run_cli_command, aiida_local_code_factory, aiida_localhost, label_first
):
    """Test ``verdi code setup`` for a remote code in non-interactive mode specifying an existing full label."""
    label = f'some-label-{label_first}'
    aiida_local_code_factory('core.arithmetic.add', '/bin/cat', computer=aiida_localhost, label=label)
    assert isinstance(load_code(label), Code)

    options = ['-n', '-D', 'd', '-P', 'core.arithmetic.add', '--on-computer', '--remote-abs-path=/remote/abs/path']

    if label_first:
        options.extend(['--label', label, '--computer', aiida_localhost.label])
    else:
        options.extend(['--computer', aiida_localhost.label, '--label', label])

    result = run_cli_command(cmd_code.setup_code, options, raises=True)
    assert f'the code `{label}@{aiida_localhost.label}` already exists.' in result.output


@pytest.mark.parametrize('non_interactive_editor', ('sleep 1; vim -cwq',), indirect=True)
def test_code_setup_local_duplicate_full_label_interactive(
    run_cli_command, aiida_local_code_factory, aiida_localhost, non_interactive_editor
):
    """Test ``verdi code setup`` for a local code in interactive mode specifying an existing full label."""
    label = 'some-label'
    code = Code(local_executable='bash', files=['/bin/bash'])
    code.label = label
    code.store()
    assert isinstance(load_code(label), Code)

    label_unique = 'label-unique'
    user_input = '\n'.join(['no', label, label_unique, 'd', 'core.arithmetic.add', '/bin', 'bash'])
    run_cli_command(cmd_code.setup_code, user_input=user_input)
    assert isinstance(load_code(label_unique), Code)


@pytest.mark.usefixtures('clear_database_before_test')
def test_code_setup_local_duplicate_full_label_non_interactive(
    run_cli_command, aiida_local_code_factory, aiida_localhost
):
    """Test ``verdi code setup`` for a local code in non-interactive mode specifying an existing full label."""
    label = 'some-label'
    code = Code(local_executable='bash', files=['/bin/bash'])
    code.label = label
    code.store()
    assert isinstance(load_code(label), Code)

    options = [
        '-n', '-D', 'd', '-P', 'core.arithmetic.add', '--store-in-db', '--code-folder=/bin', '--code-rel-path=bash',
        '--label', label
    ]

    result = run_cli_command(cmd_code.setup_code, options, raises=True)
    assert f'the code `{label}` already exists.' in result.output


@pytest.mark.usefixtures('clear_database_before_test')
def test_validate_label_uniqueness(monkeypatch, aiida_localhost):
    """Test the ``validate_label_uniqueness`` validator."""
    from aiida import orm

    def load_code(*args, **kwargs):
        raise MultipleObjectsError()

    monkeypatch.setattr(orm, 'load_code', load_code)

    ctx = click.Context(cmd_code.setup_code)
    ctx.params = {'on_computer': False}

    with pytest.raises(click.BadParameter, match=r'multiple copies of the remote code `.*` already exist.'):
        validate_label_uniqueness(ctx, None, 'some-code')

    ctx = click.Context(cmd_code.setup_code)
    ctx.params = {'on_computer': None, 'computer': aiida_localhost}

    with pytest.raises(click.BadParameter, match=r'multiple copies of the local code `.*` already exist.'):
        validate_label_uniqueness(ctx, None, 'some-code')


@pytest.mark.usefixtures('clear_database_before_test')
def test_code_test(run_cli_command):
    """Test the ``verdi code test`` command."""
    computer = Computer(
        label='test-code-computer', transport_type='core.local', hostname='localhost', scheduler_type='core.slurm'
    ).store()
    code = Code(remote_computer_exec=[computer, '/bin/invalid']).store()

    result = run_cli_command(cmd_code.code_test, [str(code.pk)], raises=True)
    assert 'Could not connect to the configured computer' in result.output

    computer.configure()

    result = run_cli_command(cmd_code.code_test, [str(code.pk)], raises=True)
    assert 'the provided remote absolute path `/bin/invalid` does not exist' in result.output

    code = Code(remote_computer_exec=[computer, '/bin/bash']).store()
    result = run_cli_command(cmd_code.code_test, [str(code.pk)])
    assert 'all tests succeeded.' in result.output
