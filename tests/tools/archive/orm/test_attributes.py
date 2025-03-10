# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Extras tests for the export and import routines"""
import pytest

from aiida import orm
from aiida.tools.archive import create_archive, get_format, import_archive


def test_import_of_attributes(tmp_path, aiida_profile):
    """Check if attributes are properly imported"""
    aiida_profile.reset_db()
    # Create Data with attributes
    data = orm.Data()
    data.label = 'my_test_data_node'
    data.set_attribute_many({'b': 2, 'c': 3})
    data.store()

    # Export
    export_file = tmp_path / 'export.aiida'
    create_archive([data], filename=export_file)

    # Clean db
    aiida_profile.reset_db()

    import_archive(export_file)
    builder = orm.QueryBuilder().append(orm.Data, filters={'label': 'my_test_data_node'})
    assert builder.count() == 1
    imported_node = builder.all(flat=True)[0]

    assert imported_node.get_attribute('b') == 2
    assert imported_node.get_attribute('c') == 3


@pytest.mark.usefixtures('clear_database_before_test')
def test_strip_checkpoints(tmp_path):
    """Test that `ProcessNode` checkpoints are stripped.

    These can be used as an attack vector through arbitrary code execution.
    """
    # Create a `ProcessNode` with a checkpoint
    process = orm.CalcJobNode()
    process.set_checkpoint({'foo': 'bar'})
    process.seal()
    process.store()

    # Export with checkpoints
    export_file = tmp_path / 'export1.aiida'
    create_archive([process], filename=export_file, strip_checkpoints=False)
    with get_format().open(export_file, 'r') as archive:
        assert archive.get(orm.ProcessNode, uuid=process.uuid).checkpoint == {'foo': 'bar'}

    # Export without checkpoints
    export_file = tmp_path / 'export2.aiida'
    create_archive([process], filename=export_file, strip_checkpoints=True)
    with get_format().open(export_file, 'r') as archive:
        assert archive.get(orm.ProcessNode, uuid=process.uuid).checkpoint is None
