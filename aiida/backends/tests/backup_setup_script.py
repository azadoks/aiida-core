# -*- coding: utf-8 -*-

import json
import shutil
import tempfile
import os

from aiida.common import utils
from aiida.common.additions.backup_script import backup_setup
from aiida.backends.settings import BACKEND
from aiida.backends.utils import is_dbenv_loaded, load_dbenv

if not is_dbenv_loaded():
    load_dbenv()

if BACKEND == "django":
    from aiida.common.additions.backup_script.backup_django import Backup
elif BACKEND == "slqalchemy":
    from aiida.common.additions.backup_script.backup_sqlalchemy import Backup
else:
    raise ValueError("Unknown backend")

__copyright__ = u"Copyright (c), This file is part of the AiiDA platform. For further information please visit http://www.aiida.net/. All rights reserved."
__license__ = "MIT license, see LICENSE.txt file."
__version__ = "0.7.0"
__authors__ = "The AiiDA team."


class TestBackupSetupScriptUnit(object):

    def tearDown(self):
        utils.raw_input = None

    def test_construct_backup_variables(self):
        """
        Test that checks that the backup variables are populated as it
        should by the construct_backup_variables by asking the needed
        questions. A lambda function is used to simulate the user input.
        """
        _backup_setup_inst = backup_setup.BackupSetup()
        ac = utils.ArrayCounter()

        # Checking parsing of backup variables with many empty answers
        answers = ["", "y", "", "y", "", "y", "1", "y", "2", "y"]
        # utils.raw_input = lambda _: answers[self.array_counter()]
        utils.raw_input = lambda _: answers[ac.array_counter()]
        bk_vars = _backup_setup_inst.construct_backup_variables("")
        # Check the parsed answers
        self.assertIsNone(bk_vars[Backup.OLDEST_OBJECT_BK_KEY])
        self.assertIsNone(bk_vars[Backup.DAYS_TO_BACKUP_KEY])
        self.assertIsNone(bk_vars[Backup.END_DATE_OF_BACKUP_KEY])
        self.assertEqual(bk_vars[Backup.PERIODICITY_KEY], 1)
        self.assertEqual(bk_vars[Backup.BACKUP_LENGTH_THRESHOLD_KEY], 2)

        # Checking parsing of backup variables with all the answers given
        ac = utils.ArrayCounter()
        answers = ["2013-07-28 20:48:53.197537+02:00", "y",
                    "2", "y", "2015-07-28 20:48:53.197537+02:00", "y",
                    "3", "y", "4", "y"]
        utils.raw_input = lambda _: answers[ac.array_counter()]
        bk_vars = _backup_setup_inst.construct_backup_variables("")
        # Check the parsed answers
        self.assertEqual(bk_vars[Backup.OLDEST_OBJECT_BK_KEY], answers[0])
        self.assertEqual(bk_vars[Backup.DAYS_TO_BACKUP_KEY], 2)
        self.assertEqual(bk_vars[Backup.END_DATE_OF_BACKUP_KEY], answers[4])
        self.assertEqual(bk_vars[Backup.PERIODICITY_KEY], 3)
        self.assertEqual(bk_vars[Backup.BACKUP_LENGTH_THRESHOLD_KEY], 4)


class TestBackupSetupScriptIntegration(object):

    def test_full_backup_setup_script(self):
        """
        This method is a full test of the backup setup script. It launches it,
        replies to all the question as the user would do and in the end it
        checks that the correct files were created with the right content.
        """
        # Create a temp folder where the backup files will be placed
        temp_folder = tempfile.mkdtemp()
        try:
            temp_aiida_folder = os.path.join(temp_folder, ".aiida")
            # The predefined answers for the setup script

            ac = utils.ArrayCounter()
            self.seq = -1
            answers = [temp_aiida_folder,   # the backup folder path
                       "",                  # should the folder be created?
                       "",                  # destination folder of the backup
                       "",                  # should the folder be created?
                       "n",                 # print config explanation?
                       "",                  # configure the backup conf file now?
                       "2014-07-18 13:54:53.688484+00:00", # start date of backup?
                       "",                  # is it correct?
                       "",                  # days to backup?
                       "",                  # is it correct?
                       "2015-04-11 13:55:53.688484+00:00", # end date of backup
                       "",                  # is it correct?
                       "1",                 # periodicity
                       "",                  # is it correct?
                       "2",                 # threshold?
                       ""]                  # is it correct?
            utils.raw_input = lambda _: answers[ac.array_counter()]

            # Run the setup script
            backup_setup.BackupSetup().run()

            # Get the backup configuration files & dirs
            backup_conf_records = [f for f in os.listdir(temp_aiida_folder)]
            # Check if all files & dirs are there
            self.assertTrue(backup_conf_records is not None and
                            len(backup_conf_records) == 4 and
                            "backup_dest" in backup_conf_records and
                            "backup_info.json.tmpl" in backup_conf_records and
                            "start_backup.py" in backup_conf_records and
                            "backup_info.json" in backup_conf_records,
                            "The created backup folder doesn't have the "
                            "expected files. "
                            "It contains: {}.".format(backup_conf_records))

            # Check the content of the main backup configuration file
            with open(os.path.join(temp_aiida_folder, "backup_info.json")
                      ) as conf_jfile:
                conf_cont = json.load(conf_jfile)
                self.assertEqual(conf_cont[Backup.OLDEST_OBJECT_BK_KEY],
                                 "2014-07-18 13:54:53.688484+00:00")
                self.assertEqual(conf_cont[Backup.DAYS_TO_BACKUP_KEY], None)
                self.assertEqual(conf_cont[Backup.END_DATE_OF_BACKUP_KEY],
                                 "2015-04-11 13:55:53.688484+00:00")
                self.assertEqual(conf_cont[Backup.PERIODICITY_KEY], 1)
                self.assertEqual(
                    conf_cont[Backup.BACKUP_LENGTH_THRESHOLD_KEY], 2)
        finally:
            shutil.rmtree(temp_folder, ignore_errors=True)
