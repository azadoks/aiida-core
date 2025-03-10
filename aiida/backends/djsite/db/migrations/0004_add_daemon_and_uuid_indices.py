# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
# pylint: disable=invalid-name
"""Database migration."""
from django.db import migrations, models

from aiida.backends.djsite.db.migrations import upgrade_schema_version

REVISION = '1.0.4'
DOWN_REVISION = '1.0.3'


class Migration(migrations.Migration):
    """Database migration."""

    dependencies = [
        ('db', '0003_add_link_type'),
    ]

    operations = [
        # Create the index that speeds up the daemon queries
        # We use the RunSQL command because Django interface
        # doesn't seem to support partial indexes
        migrations.RunSQL(
            """
        CREATE INDEX tval_idx_for_daemon
        ON db_dbattribute (tval)
        WHERE ("db_dbattribute"."tval"
        IN ('COMPUTED', 'WITHSCHEDULER', 'TOSUBMIT'))"""
        ),

        # Create an index on UUIDs to speed up loading of nodes
        # using this field
        migrations.AlterField(
            model_name='dbnode',
            name='uuid',
            field=models.CharField(max_length=36, db_index=True, editable=False, blank=True),
            preserve_default=True,
        ),
        upgrade_schema_version(REVISION, DOWN_REVISION)
    ]
