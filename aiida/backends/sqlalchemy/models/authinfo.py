# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
# pylint: disable=import-error,no-name-in-module
"""Module to manage authentification information for the SQLA backend."""

from sqlalchemy import ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column, UniqueConstraint
from sqlalchemy.types import Boolean, Integer

from .base import Base


class DbAuthInfo(Base):
    """Database model to keep computer authentication data, per user.

    Specifications are user-specific of how to submit jobs in the computer.
    The model also has an ``enabled`` logical switch that indicates whether the device is available for use or not.
    This last one can be set and unset by the user.
    """
    __tablename__ = 'db_dbauthinfo'

    id = Column(Integer, primary_key=True)  # pylint: disable=invalid-name

    aiidauser_id = Column(
        Integer, ForeignKey('db_dbuser.id', ondelete='CASCADE', deferrable=True, initially='DEFERRED')
    )
    dbcomputer_id = Column(
        Integer, ForeignKey('db_dbcomputer.id', ondelete='CASCADE', deferrable=True, initially='DEFERRED')
    )

    aiidauser = relationship('DbUser', backref='authinfos')
    dbcomputer = relationship('DbComputer', backref='authinfos')

    _metadata = Column('metadata', JSONB)
    auth_params = Column(JSONB)

    enabled = Column(Boolean, default=True)

    __table_args__ = (UniqueConstraint('aiidauser_id', 'dbcomputer_id'),)

    def __init__(self, *args, **kwargs):
        self._metadata = {}
        self.auth_params = {}
        super().__init__(*args, **kwargs)

    def __str__(self):
        if self.enabled:
            return f'DB authorization info for {self.aiidauser.email} on {self.dbcomputer.label}'
        return f'DB authorization info for {self.aiidauser.email} on {self.dbcomputer.label} [DISABLED]'
