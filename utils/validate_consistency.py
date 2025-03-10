#!/usr/bin/env python
# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Validate consistency of versions and dependencies.

Validates consistency of setup.json and

 * environment.yml
 * version in aiida/__init__.py

"""
import collections
import json
import os
import sys

import click

FILENAME_TOML = 'pyproject.toml'
FILENAME_SETUP_JSON = 'setup.json'
SCRIPT_PATH = os.path.split(os.path.realpath(__file__))[0]
ROOT_DIR = os.path.join(SCRIPT_PATH, os.pardir)
FILEPATH_SETUP_JSON = os.path.join(ROOT_DIR, FILENAME_SETUP_JSON)
FILEPATH_TOML = os.path.join(ROOT_DIR, FILENAME_TOML)


def get_setup_json():
    """Return the `setup.json` as a python dictionary """
    with open(FILEPATH_SETUP_JSON, 'r', encoding='utf8') as fil:
        return json.load(fil, object_pairs_hook=collections.OrderedDict)


def write_setup_json(data):
    """Write the contents of `data` to the `setup.json`.

    If an exception is encountered during writing, the old content is restored.

    :param data: the dictionary to write to the `setup.json`
    """
    backup = get_setup_json()

    try:
        dump_setup_json(data)
    except Exception:  # pylint: disable=broad-except
        dump_setup_json(backup)


def dump_setup_json(data):
    """Write the contents of `data` to the `setup.json`.

    .. warning:: If the writing of the file excepts, the current file will be overwritten and will be left in an
        incomplete state. To write with a backup safety use the `write_setup_json` function instead.

    :param data: the dictionary to write to the `setup.json`
    """
    with open(FILEPATH_SETUP_JSON, 'w', encoding='utf8') as handle:
        # Write with indentation of four spaces and explicitly define separators to not have spaces at end of lines
        return json.dump(data, handle, indent=4, separators=(',', ': '))


def determine_block_positions(lines, block_start_marker, block_end_marker):
    """Determine the line indices of a block in a list of lines indicated by a given start and end marker.

    :param lines: list of strings
    :param block_start_marker: string marking the beginning of the block
    :param block_end_marker: string marking the end of the block
    :return: tuple of two integers representing the line indices that indicate the start and end of the block
    """
    block_start_index = -1
    block_end_index = -1

    for line_number, line in enumerate(lines):
        if block_start_marker in line:
            block_start_index = line_number + 1

        if block_end_marker in line:
            block_end_index = line_number
            break

    if block_start_index < 0 or block_end_index < 0:
        raise RuntimeError('failed to determine the starting or end point of the block')

    return block_start_index, block_end_index


def replace_line_block(lines, block, index_start, index_end):
    """Replace a block of lines between two line indices with a new set of lines.

    :param lines: list of lines representing the whole file
    :param block: list of lines representing the new block that should be inserted after old block is removed
    :param index_start: start of the block to be removed
    :param index_end: end of the block to be removed
    :return: list of lines with block of lines replaced
    """
    # Slice out the old block by removing the lines between the markers of the block
    lines = lines[:index_start] + lines[index_end:]

    # Now insert the new block starting at the beginning of the original block
    lines[index_start:index_start] = block

    return lines


def replace_block_in_file(filepath, block_start_marker, block_end_marker, block):
    """Replace a block of text between the given string markers with the provided new block of lines.

    :param filepath: absolute path of the file
    :param block_start_marker: string marking the beginning of the block
    :param block_end_marker: string marking the end of the block
    :param block: list of lines representing the new block that should be inserted after old block is removed
    """
    with open(filepath, encoding='utf8') as handle:
        lines = handle.readlines()

    try:
        index_start, index_end = determine_block_positions(lines, block_start_marker, block_end_marker)
    except RuntimeError as exception:
        raise RuntimeError(f'problem rewriting file `{filepath}`:: {exception}')

    lines = replace_line_block(lines, block, index_start, index_end)

    with open(filepath, 'w', encoding='utf8') as handle:
        for line in lines:
            handle.write(line)


@click.group()
def cli():
    pass


@cli.command('verdi-autodocs')
def validate_verdi_documentation():
    """Auto-generate the documentation for `verdi` through `click`."""
    from click import Context

    from aiida.cmdline.commands.cmd_verdi import verdi

    width = 90  # The maximum width of the formatted help strings in characters

    # Set the `verdi data` command to isolated mode such that external plugin commands are not discovered
    ctx = Context(verdi, terminal_width=width)
    command = verdi.get_command(ctx, 'data')
    command.set_exclude_external_plugins(True)

    # Replacing the block with the commands of `verdi`
    filepath_verdi_commands = os.path.join(ROOT_DIR, 'docs', 'source', 'reference', 'command_line.rst')
    commands_block_start_marker = '.. _reference:command-line:verdi:'
    commands_block_end_marker = '.. END_OF_VERDI_COMMANDS_MARKER'

    # Generate the new block with the command help strings
    header = 'Commands'
    message = 'Below is a list with all available subcommands.'
    block = [f"{header}\n{'=' * len(header)}\n{message}\n\n"]

    for name, command in sorted(verdi.commands.items()):
        ctx = click.Context(command, terminal_width=width)

        header_label = f'.. _reference:command-line:verdi-{name}:'
        header_string = f'``verdi {name}``'
        header_underline = '-' * len(header_string)

        block.append(f'{header_label}\n\n')
        block.append(f'{header_string}\n')
        block.append(f'{header_underline}\n\n')
        block.append('.. code:: console\n\n')  # Mark the beginning of a literal block
        for line in ctx.get_help().split('\n'):
            if line:
                block.append(f'    {line}\n')
            else:
                block.append('\n')
        block.append('\n\n')

    # New block should start and end with an empty line after and before the literal block marker
    block.insert(0, '\n')
    block.append('\n')

    replace_block_in_file(filepath_verdi_commands, commands_block_start_marker, commands_block_end_marker, block)


@cli.command('version')
def validate_version():
    """Check that version numbers match.

    Check version number in setup.json and aiida-core/__init__.py and make sure they match.
    """
    import pkgutil

    # Get version from python package
    loaders = [
        module_loader for (module_loader, name, ispkg) in pkgutil.iter_modules(path=[ROOT_DIR])
        if name == 'aiida' and ispkg
    ]
    version = loaders[0].find_module('aiida').load_module('aiida').__version__

    setup_content = get_setup_json()
    if version != setup_content['version']:
        click.echo('Version number mismatch detected:')
        click.echo(f"Version number in '{FILENAME_SETUP_JSON}': {setup_content['version']}")
        click.echo(f"Version number in 'aiida/__init__.py': {version}")
        click.echo(f"Updating version in '{FILENAME_SETUP_JSON}' to: {version}")

        setup_content['version'] = version
        write_setup_json(setup_content)

        sys.exit(1)


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
