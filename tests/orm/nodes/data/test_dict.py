# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
# pylint: disable=redefined-outer-name
"""Tests for :class:`aiida.orm.nodes.data.dict.Dict` class."""
import pytest

from aiida.orm import Dict


@pytest.fixture
def dictionary():
    return {'value': 1, 'nested': {'dict': 'ionary'}}


@pytest.mark.usefixtures('clear_database_before_test')
def test_keys(dictionary):
    """Test the ``keys`` method."""
    node = Dict(dictionary)
    assert sorted(node.keys()) == sorted(dictionary.keys())


@pytest.mark.usefixtures('clear_database_before_test')
def test_get_dict(dictionary):
    """Test the ``get_dict`` method."""
    node = Dict(dictionary)
    assert node.get_dict() == dictionary


@pytest.mark.usefixtures('clear_database_before_test')
def test_dict_property(dictionary):
    """Test the ``dict`` property."""
    node = Dict(dictionary)
    assert node.dict.value == dictionary['value']
    assert node.dict.nested == dictionary['nested']


@pytest.mark.usefixtures('clear_database_before_test')
def test_get_item(dictionary):
    """Test the ``__getitem__`` method."""
    node = Dict(dictionary)
    assert node['value'] == dictionary['value']
    assert node['nested'] == dictionary['nested']


@pytest.mark.usefixtures('clear_database_before_test')
def test_set_item(dictionary):
    """Test the methods for setting the item.

    * ``__setitem__`` directly on the node
    * ``__setattr__`` through the ``AttributeManager`` returned by the ``dict`` property
    """
    node = Dict(dictionary)

    node['value'] = 2
    assert node['value'] == 2

    node.dict.value = 3
    assert node['value'] == 3


@pytest.mark.usefixtures('clear_database_before_test')
def test_correct_raises(dictionary):
    """Test that the methods for accessing the item raise the correct error.

    * ``node['inexistent']`` should raise ``KeyError``
    * ``node.dict.inexistent`` should raise ``AttributeError``
    """
    node = Dict(dictionary)

    with pytest.raises(KeyError):
        _ = node['inexistent_key']

    with pytest.raises(AttributeError):
        _ = node.dict.inexistent_key


@pytest.mark.usefixtures('clear_database_before_test')
def test_equality(dictionary):
    """Test the equality comparison for the ``Dict`` type.

    A node should compare equal to a the plain dictionary that has the same value, as well as any other ``Dict`` node
    that has the same content. For context, the discussion on whether to compare nodes by content was started in the
    following issue:

    https://github.com/aiidateam/aiida-core/issues/1917

    A summary and the final conclusion can be found in this discussion:

    https://github.com/aiidateam/aiida-core/discussions/5187
    """
    different_dict = {'I': {'am': 'different'}}
    node = Dict(dictionary)
    different_node = Dict(different_dict)
    clone = Dict(dictionary)

    # Test equality comparison with Python base type
    assert node == dictionary
    assert node != different_dict

    # Test equality comparison between `Dict` nodes
    assert node is node  # pylint: disable=comparison-with-itself
    assert node == clone
    assert node != different_node


@pytest.mark.usefixtures('clear_database_before_test')
def test_initialise_with_dict_kwarg(dictionary):
    """Test that the ``Dict`` node can be initialized with the ``dict`` keyword argument for backwards compatibility."""
    node = Dict(dict=dictionary)
    assert sorted(node.keys()) == sorted(dictionary.keys())
