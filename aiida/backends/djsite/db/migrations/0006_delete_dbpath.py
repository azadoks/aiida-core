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
from django.db import migrations

from aiida.backends.djsite.db.migrations import upgrade_schema_version

REVISION = '1.0.6'
DOWN_REVISION = '1.0.5'


class Migration(migrations.Migration):
    """Database migration."""

    dependencies = [
        ('db', '0005_add_cmtime_indices'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='dbpath',
            name='child',
        ),
        migrations.RemoveField(
            model_name='dbpath',
            name='parent',
        ),
        migrations.RemoveField(
            model_name='dbnode',
            name='children',
        ),
        migrations.DeleteModel(name='DbPath',),
        migrations.RunSQL(
            """
            DROP TRIGGER IF EXISTS autoupdate_tc ON db_dblink;
            DROP FUNCTION IF EXISTS update_tc();
        """
        ),
        upgrade_schema_version(REVISION, DOWN_REVISION)
    ]
