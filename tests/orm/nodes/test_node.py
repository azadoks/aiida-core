# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
# pylint: disable=attribute-defined-outside-init,no-member,no-self-use,too-many-public-methods,too-many-lines
"""Tests for the Node ORM class."""
from decimal import Decimal
from io import BytesIO
import logging
import os
import tempfile

import pytest

from aiida.common import LinkType, exceptions, timezone
from aiida.manage.manager import get_manager
from aiida.orm import CalculationNode, Computer, Data, Log, Node, User, WorkflowNode, load_node
from aiida.orm.utils.links import LinkTriple


@pytest.mark.usefixtures('clear_database_before_test_class')
class TestNode:
    """Tests for generic node functionality."""

    def setup_method(self):
        """Setup for methods."""
        self.user = User.objects.get_default()
        _, self.computer = Computer.objects.get_or_create(
            label='localhost',
            description='localhost computer set up by test manager',
            hostname='localhost',
            transport_type='core.local',
            scheduler_type='core.direct'
        )
        self.computer.store()

    def test_instantiate_with_user(self):
        """Test a Node can be instantiated with a specific user."""
        new_user = User(email='a@b.com').store()
        node = Data(user=new_user).store()
        assert node.user.pk == new_user.pk

    def test_instantiate_with_computer(self):
        """Test a Node can be instantiated with a specific computer."""
        node = Data(computer=self.computer).store()
        assert node.computer.pk == self.computer.pk

    def test_repository_garbage_collection(self):
        """Verify that the repository sandbox folder is cleaned after the node instance is garbage collected."""
        node = Data()
        dirpath = node._repository.backend.sandbox.abspath  # pylint: disable=protected-access

        assert os.path.isdir(dirpath)
        del node
        assert not os.path.isdir(dirpath)

    def test_computer_user_immutability(self):
        """Test that computer and user of a node are immutable after storing."""
        node = Data().store()

        with pytest.raises(exceptions.ModificationNotAllowed):
            node.computer = self.computer

        with pytest.raises(exceptions.ModificationNotAllowed):
            node.user = self.user

    @staticmethod
    def test_repository_metadata():
        """Test the basic properties for `repository_metadata`."""
        node = Data()
        assert node.repository_metadata == {}

        # Even after storing the metadata should be empty, since it contains no files
        node.store()
        assert node.repository_metadata == {}

        node = Data()
        repository_metadata = {'key': 'value'}
        node.repository_metadata = repository_metadata
        assert node.repository_metadata == repository_metadata

        node.store()
        assert node.repository_metadata != repository_metadata

    @staticmethod
    @pytest.mark.parametrize(
        'process_type, match', (
            (None, r'no process type for Node<.*>: cannot recreate process class'),
            ('aiida.calculations:core.non_existing', r'could not load process class for entry point `.*`.*'),
            ('invalid', r'could not load process class from `.*`.*'),
            ('aiida.orm.non-existing.some_function', r'could not load process class from `.*`.*'),
            ('aiida.orm.nodes.node.non-existing-function', r'could not load process class from `.*`.*'),
        )
    )
    def test_process_class_raises(process_type, match):
        """Test the ``ProcessNode.process_class`` property when it is expected to raise.

        It is not possible to load the function or class corresponding to the given process types and so the property
        should raise a ``ValueError``. The cases test from top to bottom:

         * No process type whatsoever.
         * A valid full entry point string but does not correspond to an existing entry point.
         * An invalid normal identifier (not a single dot).
         * A normal identifier for an inexisting module.
         * A normal identifier for existing module but non existing function.
        """
        node = CalculationNode(process_type=process_type)

        with pytest.raises(ValueError, match=match):
            node.process_class  # pylint: disable=pointless-statement


@pytest.mark.usefixtures('clear_database_before_test_class')
class TestNodeAttributesExtras:
    """Test for node attributes and extras."""

    def setup_method(self):
        """Setup for methods."""
        self.node = Data()

    def test_attributes(self):
        """Test the `Node.attributes` property."""
        original_attribute = {'nested': {'a': 1}}

        self.node.set_attribute('key', original_attribute)
        node_attributes = self.node.attributes
        assert node_attributes['key'] == original_attribute
        node_attributes['key']['nested']['a'] = 2

        assert original_attribute['nested']['a'] == 2

        # Now store the node and verify that `attributes` then returns a deep copy
        self.node.store()
        node_attributes = self.node.attributes

        # We change the returned node attributes but the original attribute should remain unchanged
        node_attributes['key']['nested']['a'] = 3
        assert original_attribute['nested']['a'] == 2

    def test_get_attribute(self):
        """Test the `Node.get_attribute` method."""
        original_attribute = {'nested': {'a': 1}}

        self.node.set_attribute('key', original_attribute)
        node_attribute = self.node.get_attribute('key')
        assert node_attribute == original_attribute
        node_attribute['nested']['a'] = 2

        assert original_attribute['nested']['a'] == 2

        default = 'default'
        assert self.node.get_attribute('not_existing', default=default) == default
        with pytest.raises(AttributeError):
            self.node.get_attribute('not_existing')

        # Now store the node and verify that `get_attribute` then returns a deep copy
        self.node.store()
        node_attribute = self.node.get_attribute('key')

        # We change the returned node attributes but the original attribute should remain unchanged
        node_attribute['nested']['a'] = 3
        assert original_attribute['nested']['a'] == 2

        default = 'default'
        assert self.node.get_attribute('not_existing', default=default) == default
        with pytest.raises(AttributeError):
            self.node.get_attribute('not_existing')

    def test_get_attribute_many(self):
        """Test the `Node.get_attribute_many` method."""
        original_attribute = {'nested': {'a': 1}}

        self.node.set_attribute('key', original_attribute)
        node_attribute = self.node.get_attribute_many(['key'])[0]
        assert node_attribute == original_attribute
        node_attribute['nested']['a'] = 2

        assert original_attribute['nested']['a'] == 2

        # Now store the node and verify that `get_attribute` then returns a deep copy
        self.node.store()
        node_attribute = self.node.get_attribute_many(['key'])[0]

        # We change the returned node attributes but the original attribute should remain unchanged
        node_attribute['nested']['a'] = 3
        assert original_attribute['nested']['a'] == 2

    def test_set_attribute(self):
        """Test the `Node.set_attribute` method."""
        with pytest.raises(exceptions.ValidationError):
            self.node.set_attribute('illegal.key', 'value')

        self.node.set_attribute('valid_key', 'value')
        self.node.store()

        with pytest.raises(exceptions.ModificationNotAllowed):
            self.node.set_attribute('valid_key', 'value')

    def test_set_attribute_many(self):
        """Test the `Node.set_attribute` method."""
        with pytest.raises(exceptions.ValidationError):
            self.node.set_attribute_many({'illegal.key': 'value', 'valid_key': 'value'})

        self.node.set_attribute_many({'valid_key': 'value'})
        self.node.store()

        with pytest.raises(exceptions.ModificationNotAllowed):
            self.node.set_attribute_many({'valid_key': 'value'})

    def test_reset_attribute(self):
        """Test the `Node.reset_attribute` method."""
        attributes_before = {'attribute_one': 'value', 'attribute_two': 'value'}
        attributes_after = {'attribute_three': 'value', 'attribute_four': 'value'}
        attributes_illegal = {'attribute.illegal': 'value', 'attribute_four': 'value'}

        self.node.set_attribute_many(attributes_before)
        assert self.node.attributes == attributes_before
        self.node.reset_attributes(attributes_after)
        assert self.node.attributes == attributes_after

        with pytest.raises(exceptions.ValidationError):
            self.node.reset_attributes(attributes_illegal)

        self.node.store()

        with pytest.raises(exceptions.ModificationNotAllowed):
            self.node.reset_attributes(attributes_after)

    def test_delete_attribute(self):
        """Test the `Node.delete_attribute` method."""
        self.node.set_attribute('valid_key', 'value')
        assert self.node.get_attribute('valid_key') == 'value'
        self.node.delete_attribute('valid_key')

        with pytest.raises(AttributeError):
            self.node.delete_attribute('valid_key')

        # Repeat with stored node
        self.node.set_attribute('valid_key', 'value')
        self.node.store()

        with pytest.raises(exceptions.ModificationNotAllowed):
            self.node.delete_attribute('valid_key')

    def test_delete_attribute_many(self):
        """Test the `Node.delete_attribute_many` method."""

    def test_clear_attributes(self):
        """Test the `Node.clear_attributes` method."""
        attributes = {'attribute_one': 'value', 'attribute_two': 'value'}
        self.node.set_attribute_many(attributes)
        assert self.node.attributes == attributes

        self.node.clear_attributes()
        assert self.node.attributes == {}

        # Repeat for stored node
        self.node.store()

        with pytest.raises(exceptions.ModificationNotAllowed):
            self.node.clear_attributes()

    def test_attributes_items(self):
        """Test the `Node.attributes_items` generator."""
        attributes = {'attribute_one': 'value', 'attribute_two': 'value'}
        self.node.set_attribute_many(attributes)
        assert dict(self.node.attributes_items()) == attributes

    def test_attributes_keys(self):
        """Test the `Node.attributes_keys` generator."""
        attributes = {'attribute_one': 'value', 'attribute_two': 'value'}
        self.node.set_attribute_many(attributes)
        assert set(self.node.attributes_keys()) == set(attributes)

    def test_extras(self):
        """Test the `Node.extras` property."""
        original_extra = {'nested': {'a': 1}}

        self.node.set_extra('key', original_extra)
        node_extras = self.node.extras
        assert node_extras['key'] == original_extra
        node_extras['key']['nested']['a'] = 2

        assert original_extra['nested']['a'] == 2

        # Now store the node and verify that `extras` then returns a deep copy
        self.node.store()
        node_extras = self.node.extras

        # We change the returned node extras but the original extra should remain unchanged
        node_extras['key']['nested']['a'] = 3
        assert original_extra['nested']['a'] == 2

    def test_get_extra(self):
        """Test the `Node.get_extra` method."""
        original_extra = {'nested': {'a': 1}}

        self.node.set_extra('key', original_extra)
        node_extra = self.node.get_extra('key')
        assert node_extra == original_extra
        node_extra['nested']['a'] = 2

        assert original_extra['nested']['a'] == 2

        default = 'default'
        assert self.node.get_extra('not_existing', default=default) == default
        with pytest.raises(AttributeError):
            self.node.get_extra('not_existing')

        # Now store the node and verify that `get_extra` then returns a deep copy
        self.node.store()
        node_extra = self.node.get_extra('key')

        # We change the returned node extras but the original extra should remain unchanged
        node_extra['nested']['a'] = 3
        assert original_extra['nested']['a'] == 2

        default = 'default'
        assert self.node.get_extra('not_existing', default=default) == default
        with pytest.raises(AttributeError):
            self.node.get_extra('not_existing')

    def test_get_extra_many(self):
        """Test the `Node.get_extra_many` method."""
        original_extra = {'nested': {'a': 1}}

        self.node.set_extra('key', original_extra)
        node_extra = self.node.get_extra_many(['key'])[0]
        assert node_extra == original_extra
        node_extra['nested']['a'] = 2

        assert original_extra['nested']['a'] == 2

        # Now store the node and verify that `get_extra` then returns a deep copy
        self.node.store()
        node_extra = self.node.get_extra_many(['key'])[0]

        # We change the returned node extras but the original extra should remain unchanged
        node_extra['nested']['a'] = 3
        assert original_extra['nested']['a'] == 2

    def test_set_extra(self):
        """Test the `Node.set_extra` method."""
        with pytest.raises(exceptions.ValidationError):
            self.node.set_extra('illegal.key', 'value')

        self.node.set_extra('valid_key', 'value')
        self.node.store()

        self.node.set_extra('valid_key', 'changed')
        assert load_node(self.node.pk).get_extra('valid_key') == 'changed'

    def test_set_extra_many(self):
        """Test the `Node.set_extra` method."""
        with pytest.raises(exceptions.ValidationError):
            self.node.set_extra_many({'illegal.key': 'value', 'valid_key': 'value'})

        self.node.set_extra_many({'valid_key': 'value'})
        self.node.store()

        self.node.set_extra_many({'valid_key': 'changed'})
        assert load_node(self.node.pk).get_extra('valid_key') == 'changed'

    def test_reset_extra(self):
        """Test the `Node.reset_extra` method."""
        extras_before = {'extra_one': 'value', 'extra_two': 'value'}
        extras_after = {'extra_three': 'value', 'extra_four': 'value'}
        extras_illegal = {'extra.illegal': 'value', 'extra_four': 'value'}

        self.node.set_extra_many(extras_before)
        assert self.node.extras == extras_before
        self.node.reset_extras(extras_after)
        assert self.node.extras == extras_after

        with pytest.raises(exceptions.ValidationError):
            self.node.reset_extras(extras_illegal)

        self.node.store()

        self.node.reset_extras(extras_after)
        assert load_node(self.node.pk).extras == extras_after

    def test_delete_extra(self):
        """Test the `Node.delete_extra` method."""
        self.node.set_extra('valid_key', 'value')
        assert self.node.get_extra('valid_key') == 'value'
        self.node.delete_extra('valid_key')

        with pytest.raises(AttributeError):
            self.node.delete_extra('valid_key')

        # Repeat with stored node
        self.node.set_extra('valid_key', 'value')
        self.node.store()

        self.node.delete_extra('valid_key')
        with pytest.raises(AttributeError):
            load_node(self.node.pk).get_extra('valid_key')

    def test_delete_extra_many(self):
        """Test the `Node.delete_extra_many` method."""
        self.node.set_extra('valid_key', 'value')
        assert self.node.get_extra('valid_key') == 'value'
        self.node.delete_extra('valid_key')

        with pytest.raises(AttributeError):
            self.node.delete_extra('valid_key')

        # Repeat with stored group
        self.node.set_extra('valid_key', 'value')
        self.node.store()

        self.node.delete_extra('valid_key')
        with pytest.raises(AttributeError):
            load_node(self.node.pk).get_extra('valid_key')

    def test_clear_extras(self):
        """Test the `Node.clear_extras` method."""
        extras = {'extra_one': 'value', 'extra_two': 'value'}
        self.node.set_extra_many(extras)
        assert self.node.extras == extras

        self.node.clear_extras()
        assert self.node.extras == {}

        # Repeat for stored node
        self.node.store()

        self.node.clear_extras()
        assert load_node(self.node.pk).extras == {}

    def test_extras_items(self):
        """Test the `Node.extras_items` generator."""
        extras = {'extra_one': 'value', 'extra_two': 'value'}
        self.node.set_extra_many(extras)
        assert dict(self.node.extras_items()) == extras

    def test_extras_keys(self):
        """Test the `Node.extras_keys` generator."""
        extras = {'extra_one': 'value', 'extra_two': 'value'}
        self.node.set_extra_many(extras)
        assert set(self.node.extras_keys()) == set(extras)

    def test_attribute_decimal(self):
        """Test that the `Node.set_attribute` method supports Decimal."""
        self.node.set_attribute('a_val', Decimal('3.141'))
        self.node.store()
        # ensure the returned node is a float
        assert self.node.get_attribute('a_val') == 3.141


@pytest.mark.usefixtures('clear_database_before_test_class')
class TestNodeLinks:
    """Test for linking from and to Node."""

    def setup_method(self):
        """Setup for methods."""
        self.node_source = CalculationNode()
        self.node_target = Data()

    def test_get_stored_link_triples(self):
        """Validate the `get_stored_link_triples` method."""
        data = Data().store()
        calculation = CalculationNode()

        calculation.add_incoming(data, LinkType.INPUT_CALC, 'input')
        calculation.store()
        stored_triples = calculation.get_stored_link_triples()

        assert len(stored_triples) == 1

        link_triple = stored_triples[0]

        # Verify the type and value of the tuple elements
        assert isinstance(link_triple, LinkTriple)
        assert isinstance(link_triple.node, Node)
        assert isinstance(link_triple.link_type, LinkType)
        assert link_triple.node.uuid == data.uuid
        assert link_triple.link_type == LinkType.INPUT_CALC
        assert link_triple.link_label == 'input'

    def test_validate_incoming_ipsum(self):
        """Test the `validate_incoming` method with respect to linking ourselves."""
        with pytest.raises(ValueError):
            self.node_target.validate_incoming(self.node_target, LinkType.CREATE, 'link_label')

    def test_validate_incoming(self):
        """Test the `validate_incoming` method

        For a generic Node all incoming link types are valid as long as the source is also of type Node and the link
        type is a valid LinkType enum value.
        """
        with pytest.raises(TypeError):
            self.node_target.validate_incoming(self.node_source, None, 'link_label')

        with pytest.raises(TypeError):
            self.node_target.validate_incoming(None, LinkType.CREATE, 'link_label')

        with pytest.raises(TypeError):
            self.node_target.validate_incoming(self.node_source, LinkType.CREATE.value, 'link_label')

    def test_add_incoming_create(self):
        """Nodes can only have a single incoming CREATE link, independent of the source node."""
        source_one = CalculationNode()
        source_two = CalculationNode()
        target = Data()

        target.add_incoming(source_one, LinkType.CREATE, 'link_label')

        # Can only have a single incoming CREATE link
        with pytest.raises(ValueError):
            target.validate_incoming(source_one, LinkType.CREATE, 'link_label')

        # Even when the source node is different
        with pytest.raises(ValueError):
            target.validate_incoming(source_two, LinkType.CREATE, 'link_label')

        # Or when the link label is different
        with pytest.raises(ValueError):
            target.validate_incoming(source_one, LinkType.CREATE, 'other_label')

    def test_add_incoming_call_calc(self):
        """Nodes can only have a single incoming CALL_CALC link, independent of the source node."""
        source_one = WorkflowNode()
        source_two = WorkflowNode()
        target = CalculationNode()

        target.add_incoming(source_one, LinkType.CALL_CALC, 'link_label')

        # Can only have a single incoming CALL_CALC link
        with pytest.raises(ValueError):
            target.validate_incoming(source_one, LinkType.CALL_CALC, 'link_label')

        # Even when the source node is different
        with pytest.raises(ValueError):
            target.validate_incoming(source_two, LinkType.CALL_CALC, 'link_label')

        # Or when the link label is different
        with pytest.raises(ValueError):
            target.validate_incoming(source_one, LinkType.CALL_CALC, 'other_label')

    def test_add_incoming_call_work(self):
        """Nodes can only have a single incoming CALL_WORK link, independent of the source node."""
        source_one = WorkflowNode()
        source_two = WorkflowNode()
        target = WorkflowNode()

        target.add_incoming(source_one, LinkType.CALL_WORK, 'link_label')

        # Can only have a single incoming CALL_WORK link
        with pytest.raises(ValueError):
            target.validate_incoming(source_one, LinkType.CALL_WORK, 'link_label')

        # Even when the source node is different
        with pytest.raises(ValueError):
            target.validate_incoming(source_two, LinkType.CALL_WORK, 'link_label')

        # Or when the link label is different
        with pytest.raises(ValueError):
            target.validate_incoming(source_one, LinkType.CALL_WORK, 'other_label')

    def test_add_incoming_input_calc(self):
        """Nodes can have an infinite amount of incoming INPUT_CALC links, as long as the link pair is unique."""
        source_one = Data()
        source_two = Data()
        target = CalculationNode()

        target.add_incoming(source_one, LinkType.INPUT_CALC, 'link_label')

        # Can only have a single incoming INPUT_CALC link from each source node if the label is not unique
        with pytest.raises(ValueError):
            target.validate_incoming(source_one, LinkType.INPUT_CALC, 'link_label')

        # Using another link label is fine
        target.validate_incoming(source_one, LinkType.INPUT_CALC, 'other_label')

        # However, using the same link, even from another node is illegal
        with pytest.raises(ValueError):
            target.validate_incoming(source_two, LinkType.INPUT_CALC, 'link_label')

    def test_add_incoming_input_work(self):
        """Nodes can have an infinite amount of incoming INPUT_WORK links, as long as the link pair is unique."""
        source_one = Data()
        source_two = Data()
        target = WorkflowNode()

        target.add_incoming(source_one, LinkType.INPUT_WORK, 'link_label')

        # Can only have a single incoming INPUT_WORK link from each source node if the label is not unique
        with pytest.raises(ValueError):
            target.validate_incoming(source_one, LinkType.INPUT_WORK, 'link_label')

        # Using another link label is fine
        target.validate_incoming(source_one, LinkType.INPUT_WORK, 'other_label')

        # However, using the same link, even from another node is illegal
        with pytest.raises(ValueError):
            target.validate_incoming(source_two, LinkType.INPUT_WORK, 'link_label')

    def test_add_incoming_return(self):
        """Nodes can have an infinite amount of incoming RETURN links, as long as the link triple is unique."""
        source_one = WorkflowNode()
        source_two = WorkflowNode()
        target = Data().store()  # Needs to be stored: see `test_validate_outgoing_workflow`

        target.add_incoming(source_one, LinkType.RETURN, 'link_label')

        # Can only have a single incoming RETURN link from each source node if the label is not unique
        with pytest.raises(ValueError):
            target.validate_incoming(source_one, LinkType.RETURN, 'link_label')

        # From another source node or using another label is fine
        target.validate_incoming(source_one, LinkType.RETURN, 'other_label')
        target.validate_incoming(source_two, LinkType.RETURN, 'link_label')

    def test_validate_outgoing_workflow(self):
        """Verify that attaching an unstored `Data` node with `RETURN` link from a `WorkflowNode` raises.

        This would for example be the case if a user inside a workfunction or work chain creates a new node based on its
        inputs or the outputs returned by another process and tries to attach it as an output. This would the provenance
        of that data node to be lost and should be explicitly forbidden by raising.
        """
        source = WorkflowNode()
        target = Data()

        with pytest.raises(ValueError):
            target.add_incoming(source, LinkType.RETURN, 'link_label')

    def test_get_incoming(self):
        """Test that `Node.get_incoming` will return stored and cached input links."""
        source_one = Data().store()
        source_two = Data().store()
        target = CalculationNode()

        target.add_incoming(source_one, LinkType.INPUT_CALC, 'link_one')
        target.add_incoming(source_two, LinkType.INPUT_CALC, 'link_two')

        # Without link type
        incoming_nodes = target.get_incoming().all()
        incoming_uuids = sorted([neighbor.node.uuid for neighbor in incoming_nodes])
        assert incoming_uuids == sorted([source_one.uuid, source_two.uuid])

        # Using a single link type
        incoming_nodes = target.get_incoming(link_type=LinkType.INPUT_CALC).all()
        incoming_uuids = sorted([neighbor.node.uuid for neighbor in incoming_nodes])
        assert incoming_uuids == sorted([source_one.uuid, source_two.uuid])

        # Using a link type tuple
        incoming_nodes = target.get_incoming(link_type=(LinkType.INPUT_CALC, LinkType.INPUT_WORK)).all()
        incoming_uuids = sorted([neighbor.node.uuid for neighbor in incoming_nodes])
        assert incoming_uuids == sorted([source_one.uuid, source_two.uuid])

    def test_node_indegree_unique_pair(self):
        """Test that the validation of links with indegree `unique_pair` works correctly

        The example here is a `DataNode` that has two incoming links with the same label, but with different types.
        This is legal and should pass validation.
        """
        caller = WorkflowNode().store()
        data = Data().store()
        called = CalculationNode()

        # Verify that adding two incoming links with the same link label but different type is allowed
        called.add_incoming(caller, link_type=LinkType.CALL_CALC, link_label='call')
        called.add_incoming(data, link_type=LinkType.INPUT_CALC, link_label='call')
        called.store()

        uuids_incoming = set(node.uuid for node in called.get_incoming().all_nodes())
        uuids_expected = set([caller.uuid, data.uuid])
        assert uuids_incoming == uuids_expected

    def test_node_indegree_unique_triple(self):
        """Test that the validation of links with indegree `unique_triple` works correctly

        The example here is a `DataNode` that has two incoming RETURN links with the same label, but from different
        source nodes. This is legal and should pass validation.
        """
        return_one = WorkflowNode()
        return_two = WorkflowNode()
        data = Data().store()  # Needs to be stored: see `test_validate_outgoing_workflow`

        # Verify that adding two return links with the same link label but from different source is allowed
        data.add_incoming(return_one, link_type=LinkType.RETURN, link_label='returned')
        data.add_incoming(return_two, link_type=LinkType.RETURN, link_label='returned')

        uuids_incoming = set(node.uuid for node in data.get_incoming().all_nodes())
        uuids_expected = set([return_one.uuid, return_two.uuid])
        assert uuids_incoming == uuids_expected

    def test_node_outdegree_unique_triple(self):
        """Test that the validation of links with outdegree `unique_triple` works correctly

        The example here is a `CalculationNode` that has two outgoing CREATE links with the same label, but to different
        target nodes. This is legal and should pass validation.
        """
        creator = CalculationNode().store()
        data_one = Data()
        data_two = Data()

        # Verify that adding two create links with the same link label but to different target is allowed from the
        # perspective of the source node (the CalculationNode in this case)
        data_one.add_incoming(creator, link_type=LinkType.CREATE, link_label='create')
        data_two.add_incoming(creator, link_type=LinkType.CREATE, link_label='create')
        data_one.store()
        data_two.store()

        uuids_outgoing = set(node.uuid for node in creator.get_outgoing().all_nodes())
        uuids_expected = set([data_one.uuid, data_two.uuid])
        assert uuids_outgoing == uuids_expected

    def test_get_node_by_label(self):
        """Test the get_node_by_label() method of the `LinkManager`

        In particular, check both the it returns the correct values, but also that it raises the expected
        exceptions where appropriate (missing link with a given label, or more than one link)
        """
        data = Data().store()
        calc_one_a = CalculationNode()
        calc_one_b = CalculationNode()
        calc_two = CalculationNode()

        # Two calcs using the data with the same label
        calc_one_a.add_incoming(data, link_type=LinkType.INPUT_CALC, link_label='input')
        calc_one_b.add_incoming(data, link_type=LinkType.INPUT_CALC, link_label='input')
        # A different label
        calc_two.add_incoming(data, link_type=LinkType.INPUT_CALC, link_label='the_input')

        calc_one_a.store()
        calc_one_b.store()
        calc_two.store()

        # Retrieve a link when the label is unique
        output_the_input = data.get_outgoing(link_type=LinkType.INPUT_CALC).get_node_by_label('the_input')
        assert output_the_input.pk == calc_two.pk

        with pytest.raises(exceptions.MultipleObjectsError):
            data.get_outgoing(link_type=LinkType.INPUT_CALC).get_node_by_label('input')

        with pytest.raises(exceptions.NotExistent):
            data.get_outgoing(link_type=LinkType.INPUT_CALC).get_node_by_label('some_weird_label')

    def test_tab_completable_properties(self):
        """Test properties to go from one node to a neighboring one"""
        # pylint: disable=too-many-statements
        input1 = Data().store()
        input2 = Data().store()

        top_workflow = WorkflowNode()
        workflow = WorkflowNode()
        calc1 = CalculationNode()
        calc2 = CalculationNode()

        output1 = Data().store()
        output2 = Data().store()

        # The `top_workflow` has two inputs, proxies them to `workflow`, that in turn calls two calculations, passing
        # one data node to each as input, and return the two data nodes returned one by each called calculation
        top_workflow.add_incoming(input1, link_type=LinkType.INPUT_WORK, link_label='a')
        top_workflow.add_incoming(input2, link_type=LinkType.INPUT_WORK, link_label='b')
        top_workflow.store()

        workflow.add_incoming(input1, link_type=LinkType.INPUT_WORK, link_label='a')
        workflow.add_incoming(input2, link_type=LinkType.INPUT_WORK, link_label='b')
        workflow.add_incoming(top_workflow, link_type=LinkType.CALL_WORK, link_label='CALL')
        workflow.store()

        calc1.add_incoming(input1, link_type=LinkType.INPUT_CALC, link_label='input_value')
        calc1.add_incoming(workflow, link_type=LinkType.CALL_CALC, link_label='CALL')
        calc1.store()
        output1.add_incoming(calc1, link_type=LinkType.CREATE, link_label='result')

        calc2.add_incoming(input2, link_type=LinkType.INPUT_CALC, link_label='input_value')
        calc2.add_incoming(workflow, link_type=LinkType.CALL_CALC, link_label='CALL')
        calc2.store()
        output2.add_incoming(calc2, link_type=LinkType.CREATE, link_label='result')

        output1.add_incoming(workflow, link_type=LinkType.RETURN, link_label='result_a')
        output2.add_incoming(workflow, link_type=LinkType.RETURN, link_label='result_b')
        output1.add_incoming(top_workflow, link_type=LinkType.RETURN, link_label='result_a')
        output2.add_incoming(top_workflow, link_type=LinkType.RETURN, link_label='result_b')

        # creator
        assert output1.creator.pk == calc1.pk
        assert output2.creator.pk == calc2.pk

        # caller (for calculations)
        assert calc1.caller.pk == workflow.pk
        assert calc2.caller.pk == workflow.pk

        # caller (for workflows)
        assert workflow.caller.pk == top_workflow.pk

        # .inputs for calculations
        assert calc1.inputs.input_value.pk == input1.pk
        assert calc2.inputs.input_value.pk == input2.pk
        with pytest.raises(AttributeError):
            _ = calc1.inputs.some_label

        # .inputs for workflows
        assert top_workflow.inputs.a.pk == input1.pk
        assert top_workflow.inputs.b.pk == input2.pk
        assert workflow.inputs.a.pk == input1.pk
        assert workflow.inputs.b.pk == input2.pk
        with pytest.raises(AttributeError):
            _ = workflow.inputs.some_label

        # .outputs for calculations
        assert calc1.outputs.result.pk == output1.pk
        assert calc2.outputs.result.pk == output2.pk
        with pytest.raises(AttributeError):
            _ = calc1.outputs.some_label

        # .outputs for workflows
        assert top_workflow.outputs.result_a.pk == output1.pk
        assert top_workflow.outputs.result_b.pk == output2.pk
        assert workflow.outputs.result_a.pk == output1.pk
        assert workflow.outputs.result_b.pk == output2.pk
        with pytest.raises(AttributeError):
            _ = workflow.outputs.some_label


class TestNodeDelete:
    """Tests for deleting nodes."""
    # pylint: disable=no-member,no-self-use

    @pytest.mark.usefixtures('clear_database_before_test')
    def test_delete_through_backend(self):
        """Test deletion works correctly through the backend."""
        backend = get_manager().get_backend()

        data_one = Data().store()
        data_two = Data().store()
        calculation = CalculationNode()
        calculation.add_incoming(data_one, LinkType.INPUT_CALC, 'input_one')
        calculation.add_incoming(data_two, LinkType.INPUT_CALC, 'input_two')
        calculation.store()

        log_one = Log(timezone.now(), 'test', 'INFO', data_one.pk).store()
        log_two = Log(timezone.now(), 'test', 'INFO', data_two.pk).store()

        assert len(Log.objects.get_logs_for(data_one)) == 1
        assert Log.objects.get_logs_for(data_one)[0].pk == log_one.pk
        assert len(Log.objects.get_logs_for(data_two)) == 1
        assert Log.objects.get_logs_for(data_two)[0].pk == log_two.pk

        with backend.transaction():
            backend.delete_nodes_and_connections([data_two.pk])

        assert len(Log.objects.get_logs_for(data_one)) == 1
        assert Log.objects.get_logs_for(data_one)[0].pk == log_one.pk
        assert len(Log.objects.get_logs_for(data_two)) == 0

    @pytest.mark.usefixtures('clear_database_before_test')
    def test_delete_collection_logs(self):
        """Test deletion works correctly through objects collection."""
        data_one = Data().store()
        data_two = Data().store()

        log_one = Log(timezone.now(), 'test', 'INFO', data_one.pk).store()
        log_two = Log(timezone.now(), 'test', 'INFO', data_two.pk).store()

        assert len(Log.objects.get_logs_for(data_one)) == 1
        assert Log.objects.get_logs_for(data_one)[0].pk == log_one.pk
        assert len(Log.objects.get_logs_for(data_two)) == 1
        assert Log.objects.get_logs_for(data_two)[0].pk == log_two.pk

        Node.objects.delete(data_two.pk)

        assert len(Log.objects.get_logs_for(data_one)) == 1
        assert Log.objects.get_logs_for(data_one)[0].pk == log_one.pk
        assert len(Log.objects.get_logs_for(data_two)) == 0

    @pytest.mark.usefixtures('clear_database_before_test')
    def test_delete_collection_incoming_link(self):
        """Test deletion through objects collection raises when there are incoming links."""
        data = Data().store()
        calculation = CalculationNode()
        calculation.add_incoming(data, LinkType.INPUT_CALC, 'input')
        calculation.store()

        with pytest.raises(exceptions.InvalidOperation):
            Node.objects.delete(calculation.pk)

    @pytest.mark.usefixtures('clear_database_before_test')
    def test_delete_collection_outgoing_link(self):
        """Test deletion through objects collection raises when there are outgoing links."""
        calculation = CalculationNode().store()
        data = Data()
        data.add_incoming(calculation, LinkType.CREATE, 'output')
        data.store()

        with pytest.raises(exceptions.InvalidOperation):
            Node.objects.delete(calculation.pk)


@pytest.mark.usefixtures('clear_database_before_test')
class TestNodeComments:
    """Tests for creating comments on nodes."""

    def test_add_comment(self):
        """Test comment addition."""
        data = Data().store()
        content = 'whatever Trevor'
        comment = data.add_comment(content)
        assert comment.content == content
        assert comment.node.pk == data.pk

    def test_get_comment(self):
        """Test retrieve single comment."""
        data = Data().store()
        content = 'something something dark side'
        add_comment = data.add_comment(content)
        get_comment = data.get_comment(add_comment.pk)
        assert get_comment.content == content
        assert get_comment.pk == add_comment.pk

    def test_get_comments(self):
        """Test retrieve multiple comments."""
        data = Data().store()
        data.add_comment('one')
        data.add_comment('two')
        comments = data.get_comments()
        assert {c.content for c in comments} == {'one', 'two'}

    def test_update_comment(self):
        """Test update a comment."""
        data = Data().store()
        comment = data.add_comment('original')
        data.update_comment(comment.pk, 'new')
        assert comment.content == 'new'

    def test_remove_comment(self):
        """Test remove a comment."""
        data = Data().store()
        comment = data.add_comment('original')
        assert len(data.get_comments()) == 1
        data.remove_comment(comment.pk)
        assert len(data.get_comments()) == 0


@pytest.mark.usefixtures('clear_database_before_test')
class TestNodeCaching:
    """Tests the caching behavior of the ``Node`` class."""

    def test_is_valid_cache(self):
        """Test the ``Node.is_valid_cache`` property."""
        node = Node()
        assert node.is_valid_cache

        node.is_valid_cache = False
        assert not node.is_valid_cache

        with pytest.raises(TypeError):
            node.is_valid_cache = 'false'

    def test_store_from_cache(self):
        """Regression test for storing a Node with (nested) repository content with caching."""
        data = Data()
        with tempfile.TemporaryDirectory() as tmpdir:
            dir_path = os.path.join(tmpdir, 'directory')
            os.makedirs(dir_path)
            with open(os.path.join(dir_path, 'file'), 'w', encoding='utf8') as file:
                file.write('content')
            data.put_object_from_tree(tmpdir)

        data.store()

        clone = data.clone()
        clone._store_from_cache(data, with_transaction=True)  # pylint: disable=protected-access

        assert clone.is_stored
        assert clone.get_cache_source() == data.uuid
        assert data.get_hash() == clone.get_hash()

    def test_hashing_errors(self, aiida_caplog):
        """Tests that ``get_hash`` fails in an expected manner."""
        node = Data().store()
        node.__module__ = 'unknown'  # this will inhibit package version determination
        result = node.get_hash(ignore_errors=True)
        assert result is None
        assert aiida_caplog.record_tuples == [(node.logger.name, logging.ERROR, 'Node hashing failed')]

        with pytest.raises(exceptions.HashingError, match='package version could not be determined'):
            result = node.get_hash(ignore_errors=False)
        assert result is None

    def test_uuid_equality_fallback(self):
        """Tests the fallback mechanism of checking equality by comparing uuids and hash."""
        node_0 = Data().store()

        nodepk = Data().store().pk
        node_a = load_node(pk=nodepk)
        node_b = load_node(pk=nodepk)

        assert node_a == node_b
        assert node_a != node_0
        assert node_b != node_0

        assert hash(node_a) == hash(node_b)
        assert hash(node_a) != hash(node_0)
        assert hash(node_b) != hash(node_0)


@pytest.mark.usefixtures('clear_database_before_test')
def test_iter_repo_keys():
    """Test the ``iter_repo_keys`` method."""
    data1 = Data()
    data1.put_object_from_filelike(BytesIO(b'value1'), 'key1')
    data1.put_object_from_filelike(BytesIO(b'value1'), 'key2')
    data1.put_object_from_filelike(BytesIO(b'value3'), 'folder/key3')
    data1.store()
    data2 = Data()
    data2.put_object_from_filelike(BytesIO(b'value1'), 'key1')
    data2.put_object_from_filelike(BytesIO(b'value4'), 'key2')
    data2.store()
    assert set(Data.objects.iter_repo_keys()) == {
        '31cd97ebe10a80abe1b3f401824fc2040fb8b03aafd0d37acf6504777eddee11',
        '3c9683017f9e4bf33d0fbedd26bf143fd72de9b9dd145441b75f0604047ea28e',
        '89dc6ae7f06a9f46b565af03eab0ece0bf6024d3659b7e3a1d03573cfeb0b59d'
    }
