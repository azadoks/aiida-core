# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
# pylint: disable=invalid-name,no-member
"""Delete trajectory symbols array from the repository and the reference in the attributes

Revision ID: ce56d84bcc35
Revises: 12536798d4d3
Create Date: 2019-01-21 15:35:07.280805

"""
# Remove when https://github.com/PyCQA/pylint/issues/1931 is fixed
# pylint: disable=no-member,no-name-in-module,import-error

from alembic import op
import numpy
from sqlalchemy import Integer, String, cast
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import column, func, select, table, text

from aiida.backends.general.migrations import utils

# revision identifiers, used by Alembic.
revision = 'ce56d84bcc35'
down_revision = '12536798d4d3'
branch_labels = None
depends_on = None


def upgrade():
    """Migrations for the upgrade."""
    # yapf:disable
    connection = op.get_bind()

    DbNode = table('db_dbnode', column('id', Integer), column('uuid', UUID), column('type', String),
                   column('attributes', JSONB))

    nodes = connection.execute(
        select(DbNode.c.id, DbNode.c.uuid).where(
            DbNode.c.type == op.inline_literal('node.data.array.trajectory.TrajectoryData.'))).fetchall()

    for pk, uuid in nodes:
        connection.execute(
            text(f"""UPDATE db_dbnode SET attributes = attributes #- '{{array|symbols}}' WHERE id = {pk}"""))
        utils.delete_numpy_array_from_repository(uuid, 'symbols')


def downgrade():
    """Migrations for the downgrade."""
    # yapf:disable
    connection = op.get_bind()

    DbNode = table('db_dbnode', column('id', Integer), column('uuid', UUID), column('type', String),
                   column('attributes', JSONB))

    nodes = connection.execute(
        select(DbNode.c.id, DbNode.c.uuid).where(
            DbNode.c.type == op.inline_literal('node.data.array.trajectory.TrajectoryData.'))).fetchall()

    for pk, uuid in nodes:
        attributes = connection.execute(select(DbNode.c.attributes).where(DbNode.c.id == pk)).fetchone()
        symbols = numpy.array(attributes['symbols'])
        utils.store_numpy_array_in_repository(uuid, 'symbols', symbols)
        key = op.inline_literal('{"array|symbols"}')
        connection.execute(DbNode.update().where(DbNode.c.id == pk).values(
            attributes=func.jsonb_set(DbNode.c.attributes, key, cast(list(symbols.shape), JSONB))))
