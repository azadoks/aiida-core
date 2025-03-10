# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
# pylint: disable=redefined-outer-name
"""Tests for :class:`aiida.orm.nodes.data.code.Code` class."""
import pytest

from aiida.common.exceptions import ValidationError
from aiida.orm import Code, Computer


@pytest.mark.usefixtures('clear_database_before_test')
def test_validate_remote_exec_path():
    """Test ``Code.validate_remote_exec_path``."""
    computer = Computer(
        label='test-code-computer', transport_type='core.local', hostname='localhost', scheduler_type='core.slurm'
    ).store()
    code = Code(remote_computer_exec=[computer, '/bin/invalid'])

    with pytest.raises(ValidationError, match=r'Could not connect to the configured computer.*'):
        code.validate_remote_exec_path()

    computer.configure()

    with pytest.raises(ValidationError, match=r'the provided remote absolute path `.*` does not exist.*'):
        code.validate_remote_exec_path()

    code = Code(remote_computer_exec=[computer, '/bin/bash'])
    code.validate_remote_exec_path()
