# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Modules related to the configuration of an AiiDA instance."""

# AUTO-GENERATED

# yapf: disable
# pylint: disable=wildcard-import

from .config import *
from .migrations import *
from .options import *
from .profile import *

__all__ = (
    'CURRENT_CONFIG_VERSION',
    'Config',
    'ConfigValidationError',
    'OLDEST_COMPATIBLE_CONFIG_VERSION',
    'Option',
    'Profile',
    'check_and_migrate_config',
    'config_needs_migrating',
    'config_schema',
    'get_current_version',
    'get_option',
    'get_option_names',
    'parse_option',
)

# yapf: enable

# END AUTO-GENERATED

# pylint: disable=global-statement,redefined-outer-name,wrong-import-order

__all__ += (
    'get_config', 'get_config_option', 'get_config_path', 'get_profile', 'load_documentation_profile', 'load_profile',
    'reset_config', 'reset_profile', 'CONFIG', 'PROFILE', 'BACKEND_UUID'
)

import os
import shutil
import warnings

from aiida.common.warnings import AiidaDeprecationWarning

from . import options

CONFIG = None
PROFILE = None
BACKEND_UUID = None  # This will be set to the UUID of the profile as soon as its corresponding backend is loaded


def load_profile(profile=None):
    """Load a profile.

    .. note:: if a profile is already loaded and no explicit profile is specified, nothing will be done

    :param profile: the name of the profile to load, by default will use the one marked as default in the config
    :type profile: str

    :return: the loaded `Profile` instance
    :rtype: :class:`~aiida.manage.configuration.Profile`
    :raises `aiida.common.exceptions.InvalidOperation`: if the backend of another profile has already been loaded
    """
    from aiida.common import InvalidOperation
    from aiida.common.log import configure_logging

    global PROFILE  # pylint: disable=global-variable-not-assigned
    global BACKEND_UUID  # pylint: disable=global-variable-not-assigned

    # If a profile is loaded and the specified profile name is None or that of the currently loaded, do nothing
    if PROFILE and (profile is None or PROFILE.name is profile):
        return PROFILE

    PROFILE = get_config().get_profile(profile)

    if BACKEND_UUID is not None and BACKEND_UUID != PROFILE.uuid:
        # Once the switching of profiles with different backends becomes possible, the backend has to be reset properly
        raise InvalidOperation('cannot switch profile because backend of another profile is already loaded')

    # Reconfigure the logging to make sure that profile specific logging configuration options are taken into account.
    # Note that we do not configure with `with_orm=True` because that will force the backend to be loaded. This should
    # instead be done lazily in `Manager._load_backend`.
    configure_logging()

    return PROFILE


def get_config_path():
    """Returns path to .aiida configuration directory."""
    from .settings import AIIDA_CONFIG_FOLDER, DEFAULT_CONFIG_FILE_NAME

    return os.path.join(AIIDA_CONFIG_FOLDER, DEFAULT_CONFIG_FILE_NAME)


def load_config(create=False):
    """Instantiate Config object representing an AiiDA configuration file.

    Warning: Contrary to :func:`~aiida.manage.configuration.get_config`, this function is uncached and will always
    create a new Config object. You may want to call :func:`~aiida.manage.configuration.get_config` instead.

    :param create: if True, will create the configuration file if it does not already exist
    :type create: bool

    :return: the config
    :rtype: :class:`~aiida.manage.configuration.config.Config`
    :raises aiida.common.MissingConfigurationError: if the configuration file could not be found and create=False
    """
    from aiida.common import exceptions

    from .config import Config

    filepath = get_config_path()

    if not os.path.isfile(filepath) and not create:
        raise exceptions.MissingConfigurationError(f'configuration file {filepath} does not exist')

    try:
        config = Config.from_file(filepath)
    except ValueError as exc:
        raise exceptions.ConfigurationError(f'configuration file {filepath} contains invalid JSON') from exc

    _merge_deprecated_cache_yaml(config, filepath)

    return config


def _merge_deprecated_cache_yaml(config, filepath):
    """Merge the deprecated cache_config.yml into the config."""
    from aiida.common import timezone
    cache_path = os.path.join(os.path.dirname(filepath), 'cache_config.yml')
    if not os.path.exists(cache_path):
        return

    cache_path_backup = None
    # Keep generating a new backup filename based on the current time until it does not exist
    while not cache_path_backup or os.path.isfile(cache_path_backup):
        cache_path_backup = f"{cache_path}.{timezone.now().strftime('%Y%m%d-%H%M%S.%f')}"

    warnings.warn(
        'cache_config.yml use is deprecated and support will be removed in `v3.0`. Merging into config.json and '
        f'moving to: {cache_path_backup}', AiidaDeprecationWarning
    )
    import yaml
    with open(cache_path, 'r', encoding='utf8') as handle:
        cache_config = yaml.safe_load(handle)
    for profile_name, data in cache_config.items():
        if profile_name not in config.profile_names:
            warnings.warn(f"Profile '{profile_name}' from cache_config.yml not in config.json, skipping", UserWarning)
            continue
        for key, option_name in [('default', 'caching.default_enabled'), ('enabled', 'caching.enabled_for'),
                                 ('disabled', 'caching.disabled_for')]:
            if key in data:
                value = data[key]
                # in case of empty key
                value = [] if value is None and key != 'default' else value
                config.set_option(option_name, value, scope=profile_name)
    config.store()
    shutil.move(cache_path, cache_path_backup)


def get_profile():
    """Return the currently loaded profile.

    :return: the globally loaded `Profile` instance or `None`
    :rtype: :class:`~aiida.manage.configuration.Profile`
    """
    global PROFILE  # pylint: disable=global-variable-not-assigned
    return PROFILE


def reset_profile():
    """Reset the globally loaded profile.

    .. warning:: This is experimental functionality and should for now be used only internally. If the reset is unclean
        weird unknown side-effects may occur that end up corrupting or destroying data.
    """
    global PROFILE
    global BACKEND_UUID
    PROFILE = None
    BACKEND_UUID = None


def reset_config():
    """Reset the globally loaded config.

    .. warning:: This is experimental functionality and should for now be used only internally. If the reset is unclean
        weird unknown side-effects may occur that end up corrupting or destroying data.
    """
    global CONFIG
    CONFIG = None


def get_config(create=False):
    """Return the current configuration.

    If the configuration has not been loaded yet
     * the configuration is loaded using ``load_config``
     * the global `CONFIG` variable is set
     * the configuration object is returned

    Note: This function will except if no configuration file can be found. Only call this function, if you need
    information from the configuration file.

    :param create: if True, will create the configuration file if it does not already exist
    :type create: bool

    :return: the config
    :rtype: :class:`~aiida.manage.configuration.config.Config`
    :raises aiida.common.ConfigurationError: if the configuration file could not be found, read or deserialized
    """
    global CONFIG

    if not CONFIG:
        CONFIG = load_config(create=create)

        if CONFIG.get_option('warnings.showdeprecations'):
            # If the user does not want to get AiiDA deprecation warnings, we disable them - this can be achieved with::
            #   verdi config warnings.showdeprecations False
            # Note that the AiidaDeprecationWarning does NOT inherit from DeprecationWarning
            warnings.simplefilter('default', AiidaDeprecationWarning)  # pylint: disable=no-member
            # This should default to 'once', i.e. once per different message
        else:
            warnings.simplefilter('ignore', AiidaDeprecationWarning)  # pylint: disable=no-member

    return CONFIG


def get_config_option(option_name):
    """Return the value for the given configuration option.

    This function will attempt to load the value of the option as defined for the current profile or otherwise as
    defined configuration wide. If no configuration is yet loaded, this function will fall back on the default that may
    be defined for the option itself. This is useful for options that need to be defined at loading time of AiiDA when
    no configuration is yet loaded or may not even yet exist. In cases where one expects a profile to be loaded,
    preference should be given to retrieving the option through the Config instance and its `get_option` method.

    :param option_name: the name of the configuration option
    :type option_name: str

    :return: option value as specified for the profile/configuration if loaded, otherwise option default
    """
    from aiida.common import exceptions

    option = options.get_option(option_name)

    try:
        config = get_config(create=True)
    except exceptions.ConfigurationError:
        value = option.default if option.default is not options.NO_DEFAULT else None
    else:
        if config.current_profile:
            # Try to get the option for the profile, but do not return the option default
            value_profile = config.get_option(option_name, scope=config.current_profile.name, default=False)
        else:
            value_profile = None

        # Value is the profile value if defined or otherwise the global value, which will be None if not set
        value = value_profile if value_profile else config.get_option(option_name)

    return value


def load_documentation_profile():
    """Load a dummy profile just for the purposes of being able to build the documentation.

    The building of the documentation will require importing the `aiida` package and some code will try to access the
    loaded configuration and profile, which if not done will except. On top of that, Django will raise an exception if
    the database models are loaded before its settings are loaded. This also is taken care of by loading a Django
    profile and loading the corresponding backend. Calling this function will perform all these requirements allowing
    the documentation to be built without having to install and configure AiiDA nor having an actual database present.
    """
    import tempfile

    from aiida.manage.manager import get_manager

    from .config import Config
    from .profile import Profile

    global PROFILE
    global CONFIG

    with tempfile.NamedTemporaryFile() as handle:
        profile_name = 'readthedocs'
        profile = {
            'AIIDADB_ENGINE': 'postgresql_psycopg2',
            'AIIDADB_BACKEND': 'django',
            'AIIDADB_PORT': 5432,
            'AIIDADB_HOST': 'localhost',
            'AIIDADB_NAME': 'aiidadb',
            'AIIDADB_PASS': 'aiidadb',
            'AIIDADB_USER': 'aiida',
            'AIIDADB_REPOSITORY_URI': 'file:///dev/null',
        }
        config = {'default_profile': profile_name, 'profiles': {profile_name: profile}}
        PROFILE = Profile(profile_name, profile, from_config=True)
        CONFIG = Config(handle.name, config)
        get_manager()._load_backend(schema_check=False, repository_check=False)  # pylint: disable=protected-access
