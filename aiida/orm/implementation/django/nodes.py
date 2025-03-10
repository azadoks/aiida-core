# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""Django implementation of the `BackendNode` and `BackendNodeCollection` classes."""
# pylint: disable=import-error,no-name-in-module
from datetime import datetime
from typing import Any, Dict, Iterable, Tuple

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError, transaction

from aiida.backends.djsite.db import models
from aiida.common import exceptions
from aiida.common.lang import type_check
from aiida.orm.implementation.sql.extras import SqlExtrasMixin
from aiida.orm.implementation.utils import clean_value, validate_attribute_extra_key

from . import entities
from . import utils as dj_utils
from .. import BackendNode, BackendNodeCollection
from .computers import DjangoComputer
from .users import DjangoUser


class DjangoNode(entities.DjangoModelEntity[models.DbNode], SqlExtrasMixin, BackendNode):
    """Django Node backend entity"""

    # pylint: disable=too-many-public-methods

    MODEL_CLASS = models.DbNode
    LINK_CLASS = models.DbLink

    def __init__(
        self,
        backend,
        node_type,
        user,
        computer=None,
        process_type=None,
        label='',
        description='',
        ctime=None,
        mtime=None
    ):
        """Construct a new `BackendNode` instance wrapping a new `DbNode` instance.

        :param backend: the backend
        :param node_type: the node type string
        :param user: associated `BackendUser`
        :param computer: associated `BackendComputer`
        :param label: string label
        :param description: string description
        :param ctime: The creation time as datetime object
        :param mtime: The modification time as datetime object
        """
        # pylint: disable=too-many-arguments
        super().__init__(backend)

        arguments = {
            'user': user.dbmodel,
            'node_type': node_type,
            'process_type': process_type,
            'label': label,
            'description': description,
        }

        type_check(user, DjangoUser)

        if computer:
            type_check(computer, DjangoComputer, f'computer is of type {type(computer)}')
            arguments['dbcomputer'] = computer.dbmodel

        if ctime:
            type_check(ctime, datetime, f'the given ctime is of type {type(ctime)}')
            arguments['ctime'] = ctime

        if mtime:
            type_check(mtime, datetime, f'the given mtime is of type {type(mtime)}')
            arguments['mtime'] = mtime

        self._dbmodel = dj_utils.ModelWrapper(models.DbNode(**arguments))

    def clone(self):
        """Return an unstored clone of ourselves.

        :return: an unstored `BackendNode` with the exact same attributes and extras as self
        """
        arguments = {
            'node_type': self._dbmodel.node_type,
            'process_type': self._dbmodel.process_type,
            'user': self._dbmodel.user,
            'dbcomputer': self._dbmodel.dbcomputer,
            'label': self._dbmodel.label,
            'description': self._dbmodel.description,
        }

        clone = self.__class__.__new__(self.__class__)  # pylint: disable=no-value-for-parameter
        clone.__init__(self.backend, self.node_type, self.user)
        clone._dbmodel = dj_utils.ModelWrapper(models.DbNode(**arguments))  # pylint: disable=protected-access
        return clone

    @property
    def ctime(self):
        return self._dbmodel.ctime

    @property
    def mtime(self):
        return self._dbmodel.mtime

    @property
    def uuid(self):
        return str(self._dbmodel.uuid)

    @property
    def node_type(self):
        return self._dbmodel.node_type

    @property
    def process_type(self):
        return self._dbmodel.process_type

    @process_type.setter
    def process_type(self, value):
        self._dbmodel.process_type = value

    @property
    def label(self):
        return self._dbmodel.label

    @label.setter
    def label(self, value):
        self._dbmodel.label = value

    @property
    def description(self):
        return self._dbmodel.description

    @description.setter
    def description(self, value):
        self._dbmodel.description = value

    @property
    def repository_metadata(self):
        return self._dbmodel.repository_metadata

    @repository_metadata.setter
    def repository_metadata(self, value):
        self._dbmodel.repository_metadata = value

    @property
    def computer(self):
        try:
            return self.backend.computers.from_dbmodel(self._dbmodel.dbcomputer)
        except TypeError:
            return None

    @computer.setter
    def computer(self, computer):
        type_check(computer, DjangoComputer, allow_none=True)

        if computer is not None:
            computer = computer.dbmodel

        self._dbmodel.dbcomputer = computer

    @property
    def user(self):
        return self.backend.users.from_dbmodel(self._dbmodel.user)

    @user.setter
    def user(self, user):
        type_check(user, DjangoUser)
        self._dbmodel.user = user.dbmodel

    def add_incoming(self, source, link_type, link_label):
        type_check(source, DjangoNode)

        if not self.is_stored:
            raise exceptions.ModificationNotAllowed('node has to be stored when adding an incoming link')

        if not source.is_stored:
            raise exceptions.ModificationNotAllowed('source node has to be stored when adding a link from it')

        self._add_link(source, link_type, link_label)

    def _add_link(self, source, link_type, link_label):
        """Add a link of the given type from a given node to ourself.

        :param source: the node from which the link is coming
        :param link_type: the link type
        :param link_label: the link label
        """
        savepoint_id = None

        try:
            # Transactions are needed here for Postgresql:
            # https://docs.djangoproject.com/en/1.5/topics/db/transactions/#handling-exceptions-within-postgresql-transactions
            savepoint_id = transaction.savepoint()
            self.LINK_CLASS(input_id=source.id, output_id=self.id, label=link_label, type=link_type.value).save()
            transaction.savepoint_commit(savepoint_id)
        except IntegrityError as exception:
            transaction.savepoint_rollback(savepoint_id)
            raise exceptions.UniquenessError(f'failed to create the link: {exception}') from exception

    def clean_values(self):
        self._dbmodel.attributes = clean_value(self._dbmodel.attributes)
        self._dbmodel.extras = clean_value(self._dbmodel.extras)

    def store(self, links=None, with_transaction=True, clean=True):  # pylint: disable=arguments-differ
        import contextlib

        from aiida.backends.djsite.db.models import suppress_auto_now

        if clean:
            self.clean_values()

        with transaction.atomic() if with_transaction else contextlib.nullcontext():
            with suppress_auto_now([(models.DbNode, ['mtime'])]) if self.mtime else contextlib.nullcontext():
                # We need to save the node model instance itself first such that it has a pk
                # that can be used in the foreign keys that will be needed for setting the
                # attributes and links
                self.dbmodel.save()

                if links:
                    for link_triple in links:
                        self._add_link(*link_triple)

        return self

    @property
    def attributes(self):
        return self._dbmodel.attributes

    def get_attribute(self, key: str) -> Any:
        try:
            return self._dbmodel.attributes[key]
        except KeyError as exception:
            raise AttributeError(f'attribute `{exception}` does not exist') from exception

    def set_attribute(self, key: str, value: Any) -> None:
        validate_attribute_extra_key(key)

        if self.is_stored:
            value = clean_value(value)

        self._dbmodel.attributes[key] = value
        self._flush_if_stored({'attributes'})

    def set_attribute_many(self, attributes: Dict[str, Any]) -> None:
        for key in attributes:
            validate_attribute_extra_key(key)

        if self.is_stored:
            attributes = {key: clean_value(value) for key, value in attributes.items()}

        for key, value in attributes.items():
            # We need to use `self.dbmodel` without the underscore, because otherwise the second iteration will refetch
            # what is in the database and we lose the initial changes.
            self.dbmodel.attributes[key] = value
        self._flush_if_stored({'attributes'})

    def reset_attributes(self, attributes: Dict[str, Any]) -> None:
        for key in attributes:
            validate_attribute_extra_key(key)

        if self.is_stored:
            attributes = clean_value(attributes)

        self.dbmodel.attributes = attributes
        self._flush_if_stored({'attributes'})

    def delete_attribute(self, key: str) -> None:
        try:
            self._dbmodel.attributes.pop(key)
        except KeyError as exception:
            raise AttributeError(f'attribute `{exception}` does not exist') from exception
        else:
            self._flush_if_stored({'attributes'})

    def delete_attribute_many(self, keys: Iterable[str]) -> None:
        non_existing_keys = [key for key in keys if key not in self._dbmodel.attributes]

        if non_existing_keys:
            raise AttributeError(f"attributes `{', '.join(non_existing_keys)}` do not exist")

        for key in keys:
            self.dbmodel.attributes.pop(key)

        self._flush_if_stored({'attributes'})

    def clear_attributes(self):
        self._dbmodel.attributes = {}
        self._flush_if_stored({'attributes'})

    def attributes_items(self) -> Iterable[Tuple[str, Any]]:
        for key, value in self._dbmodel.attributes.items():
            yield key, value

    def attributes_keys(self) -> Iterable[str]:
        for key in self._dbmodel.attributes.keys():
            yield key


class DjangoNodeCollection(BackendNodeCollection):
    """The collection of Node entries."""

    ENTITY_CLASS = DjangoNode

    def get(self, pk):
        try:
            return self.ENTITY_CLASS.from_dbmodel(models.DbNode.objects.get(pk=pk), self.backend)
        except ObjectDoesNotExist:
            raise exceptions.NotExistent(f"Node with pk '{pk}' not found") from ObjectDoesNotExist

    def delete(self, pk):
        try:
            models.DbNode.objects.filter(pk=pk).delete()  # pylint: disable=no-member
        except ObjectDoesNotExist:
            raise exceptions.NotExistent(f"Node with pk '{pk}' not found") from ObjectDoesNotExist
