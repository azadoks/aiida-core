.. _how-to:installation:

*******************************
How to manage your installation
*******************************


.. _how-to:installation:profile:

Managing profiles
=================

Creating profiles
-----------------
Each AiiDA installation can have multiple profiles, each of which can have its own individual database and file repository to store the contents of the :ref:`provenance graph<topics:provenance:concepts>`.
Profiles allow you to run multiple projects completely independently from one another with just a single AiiDA installation and at least one profile is required to run AiiDA.
A new profile can be created using :ref:`verdi quicksetup<reference:command-line:verdi-quicksetup>` or :ref:`verdi setup<reference:command-line:verdi-setup>`, which works similar to the former but gives more control to the user.

Listing profiles
----------------
The :ref:`verdi profile<reference:command-line:verdi-profile>` command line interface provides various commands to manage the profiles of an AiiDA installation.
To list the currently configured profiles, use ``verdi profile list``:

.. code:: bash

    Info: configuration folder: /home/user/.virtualenvs/aiida/.aiida
    * project-one
      project-two

In this particular example, there are two configured profiles, ``project-one`` and ``project-two``.
The first one is highlighted and marked with a ``*`` symbol, meaning it is the default profile.
A profile being the default means simply that any ``verdi`` command will always be executed for that profile.
You can :ref:`change the profile on a per-call basis<topics:cli:profile>` with the ``--p/--profile`` option.
To change the default profile use ``verdi profile setdefault PROFILE``.

Showing profiles
----------------
Each profile defines various parameters, such as the location of the file repository on the file system and the connection parameters for the database.
To display these parameters, use ``verdi profile show``:

.. code:: bash

    Info: Profile: project-one
    ----------------------  ------------------------------------------------
    aiidadb_backend         django
    aiidadb_engine          postgresql_psycopg2
    aiidadb_host            localhost
    aiidadb_name            aiida_project_one
    aiidadb_pass            correcthorsebatterystaple
    aiidadb_port            5432
    aiidadb_repository_uri  file:///home/user/.virtualenvs/aiida/repository/
    aiidadb_user            aiida
    default_user_email      user@email.com
    options                 {'daemon_default_workers': 3}
    profile_uuid            4c272a87d7f543b08da9fe738d88bb13
    ----------------------  ------------------------------------------------

By default, the parameters of the default profile are shown, but one can pass the profile name of another, e.g., ``verdi profile show project-two`` to change that.

Deleting profiles
-----------------
A profile can be deleted using the ``verdi profile delete`` command.
By default, deleting a profile will also delete its file repository and the database.
This behavior can be changed using the ``--skip-repository`` and ``--skip-db`` options.

.. note::

    In order to delete the database, the system user needs to have the required rights, which is not always guaranteed depending on the system.
    In such cases, the database deletion may fail and the user will have to perform the deletion manually through PostgreSQL.


.. _how-to:installation:configure:

Configuring your installation
=============================

.. _how-to:installation:configure:tab-completion:

Activating tab-completion
-------------------------
The ``verdi`` command line interface has many commands and parameters, which can be tab-completed to simplify its use.
To enable tab-completion, the following shell command should be executed (depending on the shell you use):

.. panels::
    :container: container-lg pb-3
    :column: col-lg-12 p-2

    Enable tab-completion for ``verdi`` one of the following supported shells

    .. tabbed:: bash

        .. code-block:: console

            eval "$(_VERDI_COMPLETE=bash_source verdi)"

    .. tabbed:: zsh

        .. code-block:: console

            eval "$(_VERDI_COMPLETE=zsh_source verdi)"

    .. tabbed:: fish

        .. code-block:: console

            eval (env _FOO_BAR_COMPLETE=fish_source foo-bar)


Place this command in your shell or virtual environment activation script to automatically enable tab completion when opening a new shell or activating an environment.
This file is shell specific, but likely one of the following:

    * the startup file of your shell (``.bashrc``, ``.zsh``, ...), if aiida is installed system-wide
    * the `activators <https://virtualenv.pypa.io/en/latest/user_guide.html#activators>`_ of your virtual environment
    * a `startup file <https://conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html#saving-environment-variables>`_ for your conda environment


.. important::

    After you have added the line to the start up script, make sure to restart the terminal or source the script for the changes to take effect.


.. _how-to:installation:configure:options:

Configuring profile options
---------------------------

AiiDA provides various configurational options for profiles, which can be controlled with the :ref:`verdi config<reference:command-line:verdi-config>` command.

To view all configuration options set for the current profile:

.. code:: console

    $ verdi config list
    name                                   source    value
    -------------------------------------  --------  ------------
    autofill.user.email                    global    abc@test.com
    autofill.user.first_name               global    chris
    autofill.user.institution              global    epfl
    autofill.user.last_name                global    sewell
    caching.default_enabled                default   False
    caching.disabled_for                   default
    caching.enabled_for                    default
    daemon.default_workers                 default   1
    daemon.timeout                         profile   20
    daemon.worker_process_slots            default   200
    db.batch_size                          default   100000
    logging.aiida_loglevel                 default   REPORT
    logging.alembic_loglevel               default   WARNING
    logging.circus_loglevel                default   INFO
    logging.db_loglevel                    default   REPORT
    logging.kiwipy_loglevel                default   WARNING
    logging.paramiko_loglevel              default   WARNING
    logging.plumpy_loglevel                default   WARNING
    logging.sqlalchemy_loglevel            default   WARNING
    rmq.task_timeout                       default   10
    runner.poll.interval                   profile   50
    transport.task_maximum_attempts        global    6
    transport.task_retry_initial_interval  default   20
    verdi.shell.auto_import                default
    warnings.showdeprecations              default   True

Configuration option values are taken, in order of priority, from either the profile specific setting, the global setting (applies to all profiles), or the default value.

You can also filter by a prefix:

.. code:: console

    $ verdi config list transport
    name                                   source    value
    -------------------------------------  --------  ------------
    transport.task_maximum_attempts        global    6
    transport.task_retry_initial_interval  default   20

To show the full information for a configuration option or get its current value:

.. code:: console

    $ verdi config show transport.task_maximum_attempts
    schema:
        default: 5
        description: Maximum number of transport task attempts before a Process is Paused.
        minimum: 1
        type: integer
    values:
        default: 5
        global: 6
        profile: <NOTSET>
    $ verdi config get transport.task_maximum_attempts
    6

You can also retrieve the value *via* the API:

.. code-block:: ipython

    In [1]: from aiida import get_config_option
    In [2]: get_config_option('transport.task_maximum_attempts')
    Out[2]: 6

To set a value, at the profile or global level:

.. code-block:: console

    $ verdi config set transport.task_maximum_attempts 10
    Success: 'transport.task_maximum_attempts' set to 10 for 'quicksetup' profile
    $ verdi config set --global transport.task_maximum_attempts 20
    Success: 'transport.task_maximum_attempts' set to 20 globally
    $ verdi config show transport.task_maximum_attempts
    schema:
        type: integer
        default: 5
        minimum: 1
        description: Maximum number of transport task attempts before a Process is Paused.
    values:
        default: 5
        global: 20
        profile: 10
    $ verdi config get transport.task_maximum_attempts
    10

.. tip::

    By default any option set through ``verdi config`` will be applied to the current default profile.
    To change the profile you can use the :ref:`profile option<topics:cli:profile>`.

Similarly to unset a value:

.. code-block:: console

    $ verdi config unset transport.task_maximum_attempts
    Success: 'transport.task_maximum_attempts' unset for 'quicksetup' profile
    $ verdi config unset --global transport.task_maximum_attempts
    Success: 'transport.task_maximum_attempts' unset globally
    $ verdi config show transport.task_maximum_attempts
    schema:
        type: integer
        default: 5
        minimum: 1
        description: Maximum number of transport task attempts before a Process is Paused.
    values:
        default: 5
        global: <NOTSET>
        profile: <NOTSET>
    $ verdi config get transport.task_maximum_attempts
    5

.. important::

    Changes that affect the daemon (e.g. ``logging.aiida_loglevel``) will only take affect after restarting the daemon.

.. seealso:: :ref:`How-to configure caching <how-to:run-codes:caching>`


.. _how-to:installation:configure:instance-isolation:

Isolating multiple instances
----------------------------
An AiiDA instance is defined as the installed source code plus the configuration folder that stores the configuration files with all the configured profiles.
It is possible to run multiple AiiDA instances on a single machine, simply by isolating the code and configuration in a virtual environment.

To isolate the code, make sure to install AiiDA into a virtual environment, e.g., with conda or venv, as described :ref:`here <intro:get_started:setup>`.
Whenever you activate this particular environment, you will be running the particular version of AiiDA (and all the plugins) that you installed specifically for it.

This is separate from the configuration of AiiDA, which is stored in the configuration directory which is always named ``.aiida`` and by default is stored in the home directory.
Therefore, the default path of the configuration directory is ``~/.aiida``.
By default, each AiiDA instance (each installation) will store associated profiles in this folder.
A best practice is to always separate the profiles together with the code to which they belong.
The typical approach is to place the configuration folder in the virtual environment itself and have it automatically selected whenever the environment is activated.

The location of the AiiDA configuration folder can be controlled with the ``AIIDA_PATH`` environment variable.
This allows us to change the configuration folder automatically, by adding the following lines to the activation script of a virtual environment.
For example, if the path of your virtual environment is ``/home/user/.virtualenvs/aiida``, add the following line:

.. code:: bash

    $ export AIIDA_PATH='/home/user/.virtualenvs/aiida'

Make sure to reactivate the virtual environment, if it was already active, for the changes to take effect.

.. note::

   For ``conda``, create a directory structure ``etc/conda/activate.d`` in the root folder of your conda environment (e.g. ``/home/user/miniconda/envs/aiida``), and place a file ``aiida-init.sh`` in that folder which exports the ``AIIDA_PATH``.

You can test that everything works by first echoing the environment variable with ``echo $AIIDA_PATH`` to confirm it prints the correct path.
Finally, you can check that AiiDA know also properly realizes the new location for the configuration folder by calling ``verdi profile list``.
This should display the current location of the configuration directory:

.. code:: bash

    Info: configuration folder: /home/user/.virtualenvs/aiida/.aiida
    Critical: configuration file /home/user/.virtualenvs/aiida/.aiida/config.json does not exist

The second line you will only see if you haven't yet setup a profile for this AiiDA instance.
For information on setting up a profile, refer to :ref:`creating profiles<how-to:installation:profile>`.

Besides a single path, the value of ``AIIDA_PATH`` can also be a colon-separated list of paths.
AiiDA will go through each of the paths and check whether they contain a configuration directory, i.e., a folder with the name ``.aiida``.
The first configuration directory that is encountered will be used as the configuration directory.
If no configuration directory is found, one will be created in the last path that was considered.
For example, the directory structure in your home folder ``~/`` might look like this::

    .
    ├── .aiida
    └── project_a
        ├── .aiida
        └── subfolder

If you leave the ``AIIDA_PATH`` variable unset, the default location ``~/.aiida`` will be used.
However, if you set:

.. code:: bash

    $ export AIIDA_PATH='~/project_a:'

the configuration directory ``~/project_a/.aiida`` will be used.

.. warning::

    If there was no ``.aiida`` directory in ``~/project_a``, AiiDA would have created it for you, so make sure to set the ``AIIDA_PATH`` correctly.


.. _how-to:installation:configure:daemon-as-service:

Daemon as a service
===================

The daemon can be set up as a system service, such that it automatically starts at system startup.
How to do this, is operating system specific.
For Ubuntu, here is `a template for the service file <https://github.com/marvel-nccr/ansible-role-aiida/blob/c709088dff74d1e1ae4d8379e740aba35fb2ef97/templates/aiida-daemon%40.service>`_ and `ansible instructions to install the service <https://github.com/marvel-nccr/ansible-role-aiida/blob/c709088dff74d1e1ae4d8379e740aba35fb2ef97/tasks/aiida-daemon.yml>`_.


.. _how-to:installation:performance:

Tuning performance
==================

AiiDA supports running hundreds of thousands of calculations and graphs with millions of nodes.
However, optimal performance at that scale might require some tweaks to the AiiDA configuration to balance the CPU and disk load.

Here are a few tips for tuning AiiDA performance:


    .. dropdown:: Increase the number of daemon workers

        By default, the AiiDA daemon only uses a single worker, i.e. a single operating system process.
        If ``verdi daemon status`` shows the daemon worker constantly at high CPU usage, you can use ``verdi daemon incr X`` to add ``X`` parallel daemon workers.

        Keep in mind that other processes need to run on your computer (e.g. rabbitmq, the PostgreSQL database, ...), i.e. it's a good idea to stop increasing the number of workers before you reach the number of cores of your CPU.

        To make the change permanent, set
        ::

            verdi config set daemon.default_workers 5

    .. dropdown:: Increase the number of daemon worker slots


        Each daemon worker accepts only a limited number of tasks at a time.
        If ``verdi daemon status`` constantly warns about a high percentage of the available daemon worker slots being used, you can increase the number of tasks handled by each daemon worker (thus increasing the workload per worker).
        Increasing it to 1000 should typically work.

        Set the corresponding config variable and restart the daemon
        ::

            verdi config set daemon.worker_process_slots 1000



    .. dropdown:: Prevent your operating system from indexing the file repository.

        Many Linux distributions include the ``locate`` command to quickly find files and folders, and run a daily cron job ``updatedb.mlocate`` to create the corresponding index.
        A large file repository can take a long time to index, up to the point where the hard drive is constantly indexing.

        In order to exclude the repository folder from indexing, add its path to the ``PRUNEPATH`` variable in the ``/etc/updatedb.conf`` configuration file (use ``sudo``).

    .. dropdown:: Move the Postgresql database to a fast disk (SSD), ideally on a large partition.

        1. Stop the AiiDA daemon and :ref:`back up your database <how-to:installation:backup:postgresql>`.

        2. Find the data directory of your postgres installation (something like ``/var/lib/postgresql/9.6/main``, ``/scratch/postgres/9.6/main``, ...).

            The best way is to become the postgres UNIX user and enter the postgres shell::

                psql
                SHOW data_directory;
                \q

            If you are unable to enter the postgres shell, try looking for the ``data_directory`` variable in a file ``/etc/postgresql/9.6/main/postgresql.conf`` or similar.

        3. Stop the postgres database service::

            service postgresql stop

        4. Copy all files and folders from the postgres ``data_directory`` to the new location::

            cp -a SOURCE_DIRECTORY DESTINATION_DIRECTORY

            .. note:: Flag ``-a`` will create a directory within ``DESTINATION_DIRECTORY``, e.g.::

            cp -a OLD_DIR/main/ NEW_DIR/

            creates ``NEW_DIR/main``.
            It will also keep the file permissions (necessary).

            The file permissions of the new and old directory need to be identical (including subdirectories).
            In particular, the owner and group should be both ``postgres`` (except for symbolic links in ``server.crt`` and ``server.key`` that may or may not be present).

            .. note::

                If the permissions of these links need to be changed, use the ``-h`` option of ``chown`` to avoid changing the permissions of the destination of the links.
                In case you have changed the permission of the links destination by mistake, they should typically be (beware that this might depend on your actual distribution!)::

                -rw-r--r-- 1 root root 989 Mar  1  2012 /etc/ssl/certs/ssl-cert-snakeoil.pem
                -rw-r----- 1 root ssl-cert 1704 Mar  1  2012 /etc/ssl/private/ssl-cert-snakeoil.key

        5. Point the ``data_directory`` variable in your postgres configuration file (e.g. ``/etc/postgresql/9.6/main/postgresql.conf``) to the new directory.

        6. Restart the database daemon::

            service postgresql start

        Finally, check that the data directory has indeed changed::

            psql
            SHOW data_directory;
            \q

        and try a simple AiiDA query with the new database.
        If everything went fine, you can delete the old database location.

If you're still encountering performance issues, the following tips can help with pinpointing performance bottlenecks.

    .. dropdown:: Analyze the RabbitMQ message rate

        If you're observing slow performance of the AiiDA engine, the `RabbitMQ management plugin <https://www.rabbitmq.com/management.html>`_ provides an intuitive dashboard that lets you monitor the message rate and check on what the AiiDA engine is up to.

        Enable the management plugin via something like::

            sudo rabbitmq-plugins enable rabbitmq_management

        Then, navigate to http://localhost:15672/ and log in with ``guest``/``guest``.


.. _how-to:installation:update:

Updating your installation
==========================

Whenever updating your AiiDA installation, make sure you follow these instructions **very carefully**, even when merely upgrading the patch version!
Failing to do so, may leave your installation in a broken state, or worse may even damage your data, potentially irreparably.

    1. Activate the Python environment where AiiDA is installed.
    2. Finish all running processes.
       All finished processes will be automatically migrated, but it is not possible to resume unfinished processes.
    3. Stop the daemon using ``verdi daemon stop``.
    4. :ref:`Create a backup of your database and repository<how-to:installation:backup>`.

       .. warning::

          Once you have migrated your database, you can no longer go back to an older version of ``aiida-core`` (unless you restore your database and repository from a backup).

    5. Update your ``aiida-core`` installation.

        * If you have installed AiiDA through ``conda`` simply run: ``conda update aiida-core``.
        * If you have installed AiiDA through ``pip`` simply run: ``pip install --upgrade aiida-core``.
        * If you have installed from the git repository using ``pip install -e .``, first delete all the ``.pyc`` files (``find . -name "*.pyc" -delete``) before updating your branch with ``git pull``.

    6. Migrate your database with ``verdi -p <profile_name> storage migrate``.
       Depending on the size of your database and the number of migrations to perform, data migration can take time, so please be patient.

After the database migration finishes, you will be able to continue working with your existing data.

.. note::
    If the update involved a change in the major version number of ``aiida-core``, expect backwards incompatible changes and check whether you also need to update installed plugin packages.

Updating from 0.x.* to 1.*
--------------------------
- `Additional instructions on how to migrate from 0.12.x versions <https://aiida.readthedocs.io/projects/aiida-core/en/v1.2.1/install/updating_installation.html#updating-from-0-12-to-1>`_.
- `Additional instructions on how to migrate from versions 0.4 -- 0.11 <https://aiida.readthedocs.io/projects/aiida-core/en/v1.2.1/install/updating_installation.html#older-versions>`_.
- For a list of breaking changes between the 0.x and the 1.x series of AiiDA, `see here <https://aiida.readthedocs.io/projects/aiida-core/en/v1.2.1/install/updating_installation.html#breaking-changes-from-0-12-to-1>`_.


.. _how-to:installation:backup:

.. _how-to:installation:backup:software:

Backing up your installation
============================

A full backup of an AiiDA instance and AiiDA managed data requires a backup of:

* the AiiDA configuration folder, which is typically named ``.aiida`` and located in the home folder (see also :ref:`intro:install:setup`).
  This folder contains, among other things, the ``config.json`` configuration file and log files.

* files associated with nodes in the repository folder (one per profile). Typically located in the ``.aiida`` folder.

* queryable metadata in the PostgreSQL database (one per profile).


.. todo::

    .. _how-to:installation:backup:repository:

    title: Repository backup


.. _how-to:installation:backup:postgresql:

Database backup
---------------

PostgreSQL typically spreads database information over multiple files that, if backed up directly, are not guaranteed to restore the database.
We therefore strongly recommend to periodically dump the database contents to a file (which you can then back up using your method of choice).

A few useful pointers:

* In order to avoid having to enter your database password each time you use the script, you can create a file ``.pgpass`` in your home directory containing your database credentials, as described `in the PostgreSQL documentation <https://www.postgresql.org/docs/12/libpq-pgpass.html>`_.

* In order to dump your database, use the `pg_dump utility from PostgreSQL <https://www.postgresql.org/docs/12/app-pgdump.html>`_. You can use as a starting example a bash script similar to :download:`this file <include/backup_postgresql.sh>`.

* You can setup the backup script to run daily using cron (see notes in the :ref:`previous section <how-to:installation:backup:repository>`).

.. _how-to:installation:backup:restore:

Restore backup
--------------

In order to restore a backup, you will need to:

 1. Restore the repository folder that you backed up earlier in the same location as it used to be (you can check the location in the ``config.json`` file inside your ``.aiida`` folder, or simply using ``verdi profile show``).

 2. Create an empty database following the instructions described in :ref:`database <intro:install:database>` skipping the ``verdi setup`` phase.
    The database should have the same name and database username as the original one (i.e. if you are restoring on the original postgresql cluster, you may have to either rename or delete the original database).

 3. Change directory to the folder containing the database dump created with ``pg_dump``, and load it using the ``psql`` command.

    .. dropdown:: Example commands on Linux Ubuntu

       This is an example command, assuming that your dump is named ``aiidadb-backup.psql``:

        .. code-block:: bash

          psql -h localhost -U aiida -d aiidadb -f aiidadb-backup.psql

       After supplying your database password, the database should be restored.
       Note that, if you installed the database on Ubuntu as a system service, you need to type ``sudo su - postgres`` to become the ``postgres`` UNIX user.

.. _how-to:installation:multi-user:

Managing multiple users
=======================
Setups with multiple users for a single AiiDA instance are currently not supported.
Instead, each AiiDA user should install AiiDA in a Unix/Windows account on their own computer.
Under this account it is possible to configure all the credentials necessary to connect to remote computers.
Using independent accounts will ensure that, for instance, the SSH credentials to connect to supercomputers are not shared with others.

Data can be shared between instances using :ref:`AiiDA's export and import functionality <how-to:share:archives>`.
Sharing (subsets of) the AiiDA graph can be done as often as needed.

.. _#4122: https://github.com/aiidateam/aiida-core/issues/4122
.. |Computer| replace:: :py:class:`~aiida.orm.Computer`
