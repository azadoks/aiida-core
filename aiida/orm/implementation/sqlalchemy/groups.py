# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
"""SQLA groups"""
import logging

from aiida.backends.sqlalchemy.models.group import DbGroup
from aiida.common.exceptions import UniquenessError
from aiida.common.lang import type_check
from aiida.orm.implementation.groups import BackendGroup, BackendGroupCollection
from aiida.orm.implementation.sql.extras import SqlExtrasMixin

from . import entities, users, utils

__all__ = ('SqlaGroup', 'SqlaGroupCollection')

_LOGGER = logging.getLogger(__name__)


# Unfortunately the linter doesn't seem to be able to pick up on the fact that the abstract property 'id'
# of BackendGroup is actually implemented in SqlaModelEntity so disable the abstract check
class SqlaGroup(entities.SqlaModelEntity[DbGroup], SqlExtrasMixin, BackendGroup):  # pylint: disable=abstract-method
    """The SQLAlchemy Group object"""

    MODEL_CLASS = DbGroup

    def __init__(self, backend, label, user, description='', type_string=''):
        """
        Construct a new SQLA group

        :param backend: the backend to use
        :param label: the group label
        :param user: the owner of the group
        :param description: an optional group description
        :param type_string: an optional type for the group to contain
        """
        type_check(user, users.SqlaUser)
        super().__init__(backend)

        dbgroup = DbGroup(label=label, description=description, user=user.dbmodel, type_string=type_string)
        self._dbmodel = utils.ModelWrapper(dbgroup)

    @property
    def label(self):
        return self._dbmodel.label

    @label.setter
    def label(self, label):
        """
        Attempt to change the label of the group instance. If the group is already stored
        and the another group of the same type already exists with the desired label, a
        UniquenessError will be raised

        :param label: the new group label
        :raises aiida.common.UniquenessError: if another group of same type and label already exists
        """
        self._dbmodel.label = label

        if self.is_stored:
            try:
                self._dbmodel.save()
            except Exception:
                raise UniquenessError(f'a group of the same type with the label {label} already exists') \
                    from Exception

    @property
    def description(self):
        return self._dbmodel.description

    @description.setter
    def description(self, value):
        self._dbmodel.description = value

        # Update the entry in the DB, if the group is already stored
        if self.is_stored:
            self._dbmodel.save()

    @property
    def type_string(self):
        return self._dbmodel.type_string

    @property
    def user(self):
        return self._backend.users.from_dbmodel(self._dbmodel.user)

    @user.setter
    def user(self, new_user):
        type_check(new_user, users.SqlaUser)
        self._dbmodel.user = new_user.dbmodel

    @property
    def pk(self):
        return self._dbmodel.id

    @property
    def uuid(self):
        return str(self._dbmodel.uuid)

    def __int__(self):
        if not self.is_stored:
            return None

        return self._dbnode.id  # pylint: disable=no-member

    @property
    def is_stored(self):
        return self.pk is not None

    def store(self):
        self._dbmodel.save()
        return self

    def count(self):
        """Return the number of entities in this group.

        :return: integer number of entities contained within the group
        """
        session = self.backend.get_session()
        return session.query(self.MODEL_CLASS).join(self.MODEL_CLASS.dbnodes).filter(DbGroup.id == self.pk).count()

    def clear(self):
        """Remove all the nodes from this group."""
        session = self.backend.get_session()
        # Note we have to call `dbmodel` and `_dbmodel` to circumvent the `ModelWrapper`
        self.dbmodel.dbnodes = []
        session.commit()

    @property
    def nodes(self):
        """Get an iterator to all the nodes in the group"""

        class Iterator:
            """Nodes iterator"""

            def __init__(self, dbnodes, backend):
                self._backend = backend
                self._dbnodes = dbnodes
                self.generator = self._genfunction()

            def _genfunction(self):
                for node in self._dbnodes:
                    yield self._backend.get_backend_entity(node)

            def __iter__(self):
                return self

            def __len__(self):
                return self._dbnodes.count()

            def __getitem__(self, value):
                if isinstance(value, slice):
                    return [self._backend.get_backend_entity(n) for n in self._dbnodes[value]]

                return self._backend.get_backend_entity(self._dbnodes[value])

            def __next__(self):
                return next(self.generator)

        return Iterator(self._dbmodel.dbnodes, self._backend)

    def add_nodes(self, nodes, **kwargs):
        """Add a node or a set of nodes to the group.

        :note: all the nodes *and* the group itself have to be stored.

        :param nodes: a list of `BackendNode` instance to be added to this group

        :param kwargs:
            skip_orm: When the flag is on, the SQLA ORM is skipped and SQLA is used
            to create a direct SQL INSERT statement to the group-node relationship
            table (to improve speed).
        """
        from sqlalchemy.dialects.postgresql import insert  # pylint: disable=import-error, no-name-in-module
        from sqlalchemy.exc import IntegrityError  # pylint: disable=import-error, no-name-in-module

        from aiida.backends.sqlalchemy.models.base import Base
        from aiida.orm.implementation.sqlalchemy.nodes import SqlaNode

        super().add_nodes(nodes)
        skip_orm = kwargs.get('skip_orm', False)

        def check_node(given_node):
            """ Check if given node is of correct type and stored """
            if not isinstance(given_node, SqlaNode):
                raise TypeError(f'invalid type {type(given_node)}, has to be {SqlaNode}')

            if not given_node.is_stored:
                raise ValueError('At least one of the provided nodes is unstored, stopping...')

        with utils.disable_expire_on_commit(self.backend.get_session()) as session:
            if not skip_orm:
                # Get dbnodes here ONCE, otherwise each call to dbnodes will re-read the current value in the database
                dbnodes = self._dbmodel.dbnodes

                for node in nodes:
                    check_node(node)

                    # Use pattern as suggested here:
                    # http://docs.sqlalchemy.org/en/latest/orm/session_transaction.html#using-savepoint
                    try:
                        with session.begin_nested():
                            dbnodes.append(node.dbmodel)
                            session.flush()
                    except IntegrityError:
                        # Duplicate entry, skip
                        pass
            else:
                ins_dict = []
                for node in nodes:
                    check_node(node)
                    ins_dict.append({'dbnode_id': node.id, 'dbgroup_id': self.id})

                my_table = Base.metadata.tables['db_dbgroup_dbnodes']
                ins = insert(my_table).values(ins_dict)
                session.execute(ins.on_conflict_do_nothing(index_elements=['dbnode_id', 'dbgroup_id']))

            # Commit everything as up till now we've just flushed
            session.commit()

    def remove_nodes(self, nodes, **kwargs):
        """Remove a node or a set of nodes from the group.

        :note: all the nodes *and* the group itself have to be stored.

        :param nodes: a list of `BackendNode` instance to be added to this group
        :param kwargs:
            skip_orm: When the flag is set to `True`, the SQLA ORM is skipped and SQLA is used to create a direct SQL
            DELETE statement to the group-node relationship table in order to improve speed.
        """
        from sqlalchemy import and_

        from aiida.backends.sqlalchemy.models.base import Base
        from aiida.orm.implementation.sqlalchemy.nodes import SqlaNode

        super().remove_nodes(nodes)

        # Get dbnodes here ONCE, otherwise each call to dbnodes will re-read the current value in the database
        dbnodes = self._dbmodel.dbnodes
        skip_orm = kwargs.get('skip_orm', False)

        def check_node(node):
            if not isinstance(node, SqlaNode):
                raise TypeError(f'invalid type {type(node)}, has to be {SqlaNode}')

            if node.id is None:
                raise ValueError('At least one of the provided nodes is unstored, stopping...')

        list_nodes = []

        with utils.disable_expire_on_commit(self.backend.get_session()) as session:
            if not skip_orm:
                for node in nodes:
                    check_node(node)

                    # Check first, if SqlA issues a DELETE statement for an unexisting key it will result in an error
                    if node.dbmodel in dbnodes:
                        list_nodes.append(node.dbmodel)

                for node in list_nodes:
                    dbnodes.remove(node)
            else:
                table = Base.metadata.tables['db_dbgroup_dbnodes']
                for node in nodes:
                    check_node(node)
                    clause = and_(table.c.dbnode_id == node.id, table.c.dbgroup_id == self.id)
                    statement = table.delete().where(clause)
                    session.execute(statement)

            session.commit()


class SqlaGroupCollection(BackendGroupCollection):
    """The SLQA collection of groups"""

    ENTITY_CLASS = SqlaGroup

    def delete(self, id):  # pylint: disable=redefined-builtin
        session = self.backend.get_session()

        session.get(DbGroup, id).delete()
        session.commit()
