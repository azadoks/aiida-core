# -*- coding: utf-8 -*-
###########################################################################
# Copyright (c), The AiiDA team. All rights reserved.                     #
# This file is part of the AiiDA code.                                    #
#                                                                         #
# The code is hosted on GitHub at https://github.com/aiidateam/aiida-core #
# For further information on the license, see the LICENSE.txt file        #
# For further information please visit http://www.aiida.net               #
###########################################################################
# pylint: disable=no-self-use
""""Implementation of `DbImporter` for the OQMD database."""
from aiida.tools.dbimporters.baseclasses import CifEntry, DbImporter, DbSearchResults


class OqmdDbImporter(DbImporter):
    """
    Database importer for Open Quantum Materials Database.
    """

    def _str_clause(self, key, alias, values):
        """
        Returns part of HTTP GET query for querying string fields.
        """
        if not isinstance(values, str) and not isinstance(values, int):
            raise ValueError(f"incorrect value for keyword '{alias}' -- only strings and integers are accepted")
        return f'{key}={values}'

    _keywords = {'element': ['element', None]}

    def __init__(self, **kwargs):
        self._query_url = 'http://oqmd.org'
        self.setup_db(**kwargs)

    def query_get(self, **kwargs):
        """
        Forms a HTTP GET query for querying the OQMD database.

        :return: a strings for HTTP GET statement.
        """
        elements = []
        if 'element' in kwargs:
            elements = kwargs.pop('element')
        if not isinstance(elements, list):
            elements = [elements]

        return f"{self._query_url}/materials/composition/{''.join(elements)}"

    def query(self, **kwargs):
        """
        Performs a query on the OQMD database using ``keyword = value`` pairs,
        specified in ``kwargs``.

        :return: an instance of
            :py:class:`aiida.tools.dbimporters.plugins.oqmd.OqmdSearchResults`.
        """
        import re
        from urllib.request import urlopen

        query_statement = self.query_get(**kwargs)
        with urlopen(query_statement) as handle:
            response = handle.read()
        entries = re.findall(r'(/materials/entry/\d+)', response)

        results = []
        for entry in entries:
            with urlopen(f'{self._query_url}{entry}') as handle:
                response = handle.read()
            structures = re.findall(r'/materials/export/conventional/cif/(\d+)', response)
            for struct in structures:
                results.append({'id': struct})

        return OqmdSearchResults(results)

    def setup_db(self, query_url=None, **kwargs):  # pylint: disable=arguments-differ
        """
        Changes the database connection details.
        """
        if query_url:
            self._query_url = query_url

        if kwargs:
            raise NotImplementedError(f"following keyword(s) are not implemented: {', '.join(kwargs.keys())}")

    def get_supported_keywords(self):
        """
        Returns the list of all supported query keywords.

        :return: list of strings
        """
        return self._keywords.keys()


class OqmdSearchResults(DbSearchResults):  # pylint: disable=abstract-method
    """
    Results of the search, performed on OQMD.
    """
    _base_url = 'http://oqmd.org/materials/export/conventional/cif/'

    def __init__(self, results):
        super().__init__(results)
        self._return_class = OqmdEntry

    def __len__(self):
        return len(self._results)

    def _get_source_dict(self, result_dict):
        """
        Returns a dictionary, which is passed as kwargs to the created
        DbEntry instance, describing the source of the entry.

        :param result_dict: dictionary, describing an entry in the results.
        """
        return {'id': result_dict['id']}

    def _get_url(self, result_dict):
        """
        Returns an URL of an entry CIF file.

        :param result_dict: dictionary, describing an entry in the results.
        """
        return self._base_url + result_dict['id']


class OqmdEntry(CifEntry):  # pylint: disable=abstract-method
    """
    Represents an entry from OQMD.
    """

    def __init__(self, uri, **kwargs):
        """
        Creates an instance of
        :py:class:`aiida.tools.dbimporters.plugins.oqmd.OqmdEntry`, related
        to the supplied URI.
        """
        super().__init__(db_name='Open Quantum Materials Database', db_uri='http://oqmd.org', uri=uri, **kwargs)
