# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""SqlAlchemy implementations for the `Computer` entity and collection."""

from copy import copy

# pylint: disable=import-error,no-name-in-module
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm.session import make_transient

from aiida.backends.sqlalchemy.models.computer import DbComputer
from aiida.common import exceptions
from aiida.orm.implementation.computers import BackendComputer, BackendComputerCollection

from . import entities, utils


class SqlaComputer(entities.SqlaModelEntity[DbComputer], BackendComputer):
    """SqlAlchemy implementation for `BackendComputer`."""

    # pylint: disable=too-many-public-methods

    MODEL_CLASS = DbComputer

    def __init__(self, backend, **kwargs):
        super().__init__(backend)
        self._dbmodel = utils.ModelWrapper(DbComputer(**kwargs))

    @property
    def uuid(self):
        return str(self._dbmodel.uuid)

    @property
    def pk(self):
        return self._dbmodel.id

    @property
    def id(self):  # pylint: disable=invalid-name
        return self._dbmodel.id

    @property
    def is_stored(self):
        return self._dbmodel.id is not None

    def copy(self):
        """Create an unstored clone of an already stored `Computer`."""
        session = self.backend.get_session()

        if not self.is_stored:
            raise exceptions.InvalidOperation('You can copy a computer only after having stored it')

        dbcomputer = copy(self._dbmodel)
        make_transient(dbcomputer)
        session.add(dbcomputer)

        newobject = self.__class__.from_dbmodel(dbcomputer)  # pylint: disable=no-value-for-parameter

        return newobject

    def store(self):
        """Store the `Computer` instance."""
        try:
            self._dbmodel.save()
        except SQLAlchemyError:
            raise ValueError('Integrity error, probably the hostname already exists in the DB')

        return self

    @property
    def label(self):
        return self._dbmodel.label

    @property
    def description(self):
        return self._dbmodel.description

    @property
    def hostname(self):
        return self._dbmodel.hostname

    def get_metadata(self):
        return self._dbmodel._metadata  # pylint: disable=protected-access

    def set_metadata(self, metadata):
        self._dbmodel._metadata = metadata  # pylint: disable=protected-access

    def set_label(self, val):
        self._dbmodel.label = val

    def set_hostname(self, val):
        self._dbmodel.hostname = val

    def set_description(self, val):
        self._dbmodel.description = val

    def get_scheduler_type(self):
        return self._dbmodel.scheduler_type

    def set_scheduler_type(self, scheduler_type):
        self._dbmodel.scheduler_type = scheduler_type

    def get_transport_type(self):
        return self._dbmodel.transport_type

    def set_transport_type(self, transport_type):
        self._dbmodel.transport_type = transport_type


class SqlaComputerCollection(BackendComputerCollection):
    """Collection of `Computer` instances."""

    ENTITY_CLASS = SqlaComputer

    def list_names(self):
        session = self.backend.get_session()
        return session.query(DbComputer.label).all()

    def delete(self, pk):
        try:
            session = self.backend.get_session()
            session.get(DbComputer, pk).delete()
            session.commit()
        except SQLAlchemyError as exc:
            raise exceptions.InvalidOperation(
                'Unable to delete the requested computer: it is possible that there '
                'is at least one node using this computer (original message: {})'.format(exc)
            )
