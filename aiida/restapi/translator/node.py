from aiida.restapi.translator.base import BaseTranslator
from aiida.restapi.caching import cache
from aiida.common.exceptions import InputValidationError, ValidationError, \
    InvalidOperation
from aiida.restapi.common.exceptions import RestValidationError
from aiida.restapi.common.config import CACHING_TIMEOUTS, custom_schema


class NodeTranslator(BaseTranslator):
    """
    TODO add docstring

    """

    # A label associated to the present class (coincides with the resource name)
    __label__ = "nodes"
    # The string name of the AiiDA class one-to-one associated to the present
    #  class
    _aiida_type = "node.Node"
    # The string associated to the AiiDA class in the query builder lexicon
    _qb_type = _aiida_type + '.'

    _result_type = __label__

    _content_type = None
    _default_projections = custom_schema['columns'][__label__]
    _alist = None
    _nalist = None
    _elist = None
    _nelist = None

    def __init__(self):
        """
        Initialise the parameters.
        Create the basic query_help
        """
        # basic query_help object
        super(NodeTranslator, self).__init__()


    def set_query_type(self, query_type, alist=None, nalist=None, elist=None,
                       nelist=None):
        """
        sets one of the mutually exclusive values for self._result_type and
        self._content_type.
        :param query_type:(string) the value assigned to either variable.
        """

        if query_type == "default":
            pass
        elif query_type == "inputs":
            self._result_type = 'input_of'
        elif query_type == "outputs":
            self._result_type = "output_of"
        elif query_type == "attributes":
            self._content_type = "attributes"
            self._alist = alist
            self._nalist = nalist
        elif query_type == "extras":
            self._content_type = "extras"
            self._elist = elist
            self._nelist = nelist
        else:
            raise InputValidationError("invalid result/content value: {"
                                       "}".format(query_type))

        ## Add input/output relation to the query help
        if self._result_type is not self.__label__:
            self._query_help["path"].append(
                {
                "type": "node.Node.",
                "label": self._result_type,
                self._result_type: self.__label__
                })


    def set_query(self, filters=None, orders=None, projections=None,
                  query_type=None, pk=None, alist=None, nalist=None,
                  elist=None, nelist=None):
        """
        Adds filters, default projections, order specs to the query_help,
        and initializes the qb object

        :param filters: dictionary with the filters
        :param orders: dictionary with the order for each tag
        :param projections: dictionary with the projection. It is discarded
        if query_type=='attributes'/'extras'
        :param query_type: (string) specify the result or the content (
        "attr")
        :param pk: (integer) pk of a specific node
        """

        ## Check the compatibility of query_type and pk
        if query_type is not "default" and pk is None:
            raise ValidationError("non default result/content can only be "
                                  "applied to a specific pk")

        ## Set the type of query
        self.set_query_type(query_type, alist=alist, nalist=nalist,
                            elist=elist, nelist=nelist)

        ## Define projections
        if self._content_type is not None:
            # Use '*' so that the object itself will be returned.
            # In get_results() we access attributes/extras by
            # calling the get_attrs()/get_extras().
            projections = ['*']
        else:
            pass #i.e. use the input parameter projection

        ## TODO this actually works, but the logic is a little bit obscure.
        # Make it clearer
        if self._result_type is not self.__label__:
            projections = self._default_projections

        super(NodeTranslator, self).set_query(filters=filters,
                                              orders=orders,
                                              projections=projections,
                                              pk=pk)


    def _get_content(self):
        """
        Used by get_results() in case of endpoint include "content" option
        :return: data: a dictionary containing the results obtained by
        running the query
        """
        if not self._is_qb_initialized:
            raise InvalidOperation("query builder object has not been "
                                    "initialized.")

        ## Initialization
        data = {}

        ## Count the total number of rows returned by the query (if not
        # already done)
        if self._total_count is None:
            self.count()

        if self._total_count > 0:
            n = self.qb.first()[0]
            if self._content_type == "attributes":
                # Get all attrs if nalist and alist are both None
                if self._alist is None and self._nalist is None:
                    data[self._content_type] = n.get_attrs()
                # Get all attrs except those contained in nalist
                elif self._alist is None and self._nalist is not None:
                    attrs = {}
                    for key in n.get_attrs().keys():
                        if key not in self._nalist:
                            attrs[key] = n.get_attr(key)
                    data[self._content_type] = attrs
                # Get all attrs contained in alist
                elif self._alist is not None and self._nalist is None:
                    attrs = {}
                    for key in n.get_attrs().keys():
                        if key in self._alist:
                            attrs[key] = n.get_attr(key)
                    data[self._content_type] = attrs
                else:
                    raise RestValidationError("you cannot specify both alist "
                                              "and nalist")
            elif self._content_type == "extras":
                # Get all extras if nelist and elist are both None
                if self._elist is None and self._nelist is None:
                    data[self._content_type] = n.get_extras()
                # Get all extras except those contained in nelist
                elif self._elist is None and self._nelist is not None:
                    extras = {}
                    for key in n.get_extras().keys():
                        if key not in self._nelist:
                            extras[key] = n.get_extra(key)
                    data[self._content_type] = extras
                # Get all extras contained in elist
                elif self._elist is not None and self._nelist is None:
                    extras = {}
                    for key in n.get_extras().keys():
                        if key in self._elist:
                            extras[key] = n.get_extra(key)
                    data[self._content_type] = extras
                else:
                    raise RestValidationError("you cannot specify both elist "
                                              "and nelist")
            else:
                raise ValidationError("invalid content type")
                # Default case
        else:
            pass

        return data

    def get_results(self):
        """
        Returns either a list of nodes or details of single node from database

        :return: either a list of nodes or the details of single node
        from the database
        """
        if self._content_type is not None:
            return self._get_content()
        else:
            return super(NodeTranslator, self).get_results()

