# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""`verdi status` command."""
import enum
import sys

import click

from aiida.cmdline.commands.cmd_verdi import verdi
from aiida.cmdline.params import options
from aiida.cmdline.utils import echo
from aiida.common.exceptions import IncompatibleDatabaseSchema
from aiida.common.log import override_log_level

from ..utils.echo import ExitCode  # pylint: disable=import-error,no-name-in-module


class ServiceStatus(enum.IntEnum):
    """Describe status of services for 'verdi status' command."""
    UP = 0  # pylint: disable=invalid-name
    ERROR = 1
    WARNING = 2
    DOWN = 3


STATUS_SYMBOLS = {
    ServiceStatus.UP: {
        'color': 'green',
        'string': '\u2714',
    },
    ServiceStatus.ERROR: {
        'color': 'red',
        'string': '\u2718',
    },
    ServiceStatus.WARNING: {
        'color': 'yellow',
        'string': '\u23FA',
    },
    ServiceStatus.DOWN: {
        'color': 'red',
        'string': '\u2718',
    },
}


@verdi.command('status')
@options.PRINT_TRACEBACK()
@click.option('--no-rmq', is_flag=True, help='Do not check RabbitMQ status')
def verdi_status(print_traceback, no_rmq):
    """Print status of AiiDA services."""
    # pylint: disable=broad-except,too-many-statements,too-many-branches,too-many-locals,
    from aiida import __version__
    from aiida.cmdline.utils.daemon import delete_stale_pid_file, get_daemon_status
    from aiida.common.utils import Capturing
    from aiida.manage.configuration.settings import AIIDA_CONFIG_FOLDER
    from aiida.manage.manager import get_manager

    exit_code = ExitCode.SUCCESS

    print_status(ServiceStatus.UP, 'version', f'AiiDA v{__version__}')
    print_status(ServiceStatus.UP, 'config', AIIDA_CONFIG_FOLDER)

    manager = get_manager()

    try:
        profile = manager.get_profile()

        if profile is None:
            print_status(ServiceStatus.WARNING, 'profile', 'no profile configured yet')
            echo.echo_report('Configure a profile by running `verdi quicksetup` or `verdi setup`.')
            return

        print_status(ServiceStatus.UP, 'profile', profile.name)

    except Exception as exc:
        message = 'Unable to read AiiDA profile'
        print_status(ServiceStatus.ERROR, 'profile', message, exception=exc, print_traceback=print_traceback)
        sys.exit(ExitCode.CRITICAL)  # stop here - without a profile we cannot access anything

    # Getting the repository
    try:
        repository = manager.get_backend().get_repository()
    except Exception as exc:
        message = 'Error with repository folder'
        print_status(ServiceStatus.ERROR, 'repository', message, exception=exc, print_traceback=print_traceback)
        exit_code = ExitCode.CRITICAL
    else:
        repository_status = f'Connected to {repository}'
        print_status(ServiceStatus.UP, 'repository', repository_status)

    # Getting the postgres status by trying to get a database cursor
    backend_manager = manager.get_backend_manager()
    dbgen = backend_manager.get_schema_generation_database()
    dbver = backend_manager.get_schema_version_backend()
    database_data = [
        profile.database_name, dbgen, dbver, profile.database_username, profile.database_hostname, profile.database_port
    ]
    try:
        with override_log_level():  # temporarily suppress noisy logging
            backend = manager.get_backend()
            backend.cursor()

    except IncompatibleDatabaseSchema:
        message = f'Database schema {dbgen} / {dbver} (generation/version) is incompatible with the code. '
        message += 'Run `verdi storage migrate` to solve this.'
        print_status(ServiceStatus.DOWN, 'postgres', message)
        exit_code = ExitCode.CRITICAL

    except Exception as exc:
        message = 'Unable to connect to database `{}` with schema {} / {} (generation/version) as {}@{}:{}'.format(
            *database_data
        )
        print_status(ServiceStatus.DOWN, 'postgres', message, exception=exc, print_traceback=print_traceback)
        exit_code = ExitCode.CRITICAL

    else:
        message = 'Connected to database `{}` with schema {} / {} (generation/version) as {}@{}:{}'.format(
            *database_data
        )
        print_status(ServiceStatus.UP, 'postgres', message)

    # Getting the rmq status
    if not no_rmq:
        try:
            with Capturing(capture_stderr=True):
                with override_log_level():  # temporarily suppress noisy logging
                    comm = manager.create_communicator(with_orm=False)
                    comm.close()
        except Exception as exc:
            message = f'Unable to connect to rabbitmq with URL: {profile.get_rmq_url()}'
            print_status(ServiceStatus.ERROR, 'rabbitmq', message, exception=exc, print_traceback=print_traceback)
            exit_code = ExitCode.CRITICAL
        else:
            print_status(ServiceStatus.UP, 'rabbitmq', f'Connected as {profile.get_rmq_url()}')

    # Getting the daemon status
    try:
        client = manager.get_daemon_client()
        delete_stale_pid_file(client)
        daemon_status = get_daemon_status(client)

        daemon_status = daemon_status.split('\n', maxsplit=1)[0]  # take only the first line
        if client.is_daemon_running:
            print_status(ServiceStatus.UP, 'daemon', daemon_status)
        else:
            print_status(ServiceStatus.WARNING, 'daemon', daemon_status)

    except Exception as exc:
        message = 'Error getting daemon status'
        print_status(ServiceStatus.ERROR, 'daemon', message, exception=exc, print_traceback=print_traceback)
        exit_code = ExitCode.CRITICAL

    # Note: click does not forward return values to the exit code, see https://github.com/pallets/click/issues/747
    sys.exit(exit_code)


def print_status(status, service, msg='', exception=None, print_traceback=False):
    """Print status message.

    Includes colored indicator.

    :param status: a ServiceStatus code
    :param service: string for service name
    :param msg:  message string
    """
    symbol = STATUS_SYMBOLS[status]
    echo.echo(f" {symbol['string']} ", fg=symbol['color'], nl=False)
    echo.echo(f"{service + ':':12s} {msg}")

    if exception is not None:
        echo.echo_error(f'{type(exception).__name__}: {exception}')

    if print_traceback:
        import traceback
        traceback.print_exc()
