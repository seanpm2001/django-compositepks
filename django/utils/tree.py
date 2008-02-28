"""
A class for storing a tree graph. Primarily used for filter constructs in the
ORM.
"""

from copy import deepcopy

class Node(object):
    """
    A single internal node in the tree graph. A Node should be viewed as a
    connection (the root) with the children being either leaf nodes or other
    Node instances.
    """
    # Standard connector type. Clients usually won't use this at all and
    # subclasses will usually override the value.
    default = 'DEFAULT'

    def __init__(self, children=None, connector=None, negated=False):
        self.children = children and children[:] or []
        self.connector = connector or self.default
        self.subtree_parents = []
        self.negated = negated

    def __str__(self):
        if self.negated:
            return '(NOT (%s: %s))' % (self.connector, ', '.join([str(c) for c
                    in self.children]))
        return '(%s: %s)' % (self.connector, ', '.join([str(c) for c in
                self.children]))

    def __deepcopy__(self, memodict):
        """
        Utility method used by copy.deepcopy().
        """
        obj = Node(connector=self.connector, negated=self.negated)
        obj.__class__ = self.__class__
        obj.children = deepcopy(self.children, memodict)
        obj.subtree_parents = deepcopy(self.subtree_parents, memodict)
        return obj

    def __len__(self):
        """
        The size of a node if the number of children it has.
        """
        return len(self.children)

    def __nonzero__(self):
        """
        For truth value testing.
        """
        return bool(self.children)

    def __contains__(self, other):
        """
        Returns True is 'other' is a direct child of this instance.
        """
        return other in self.children

    def add(self, node, conn_type):
        """
        Adds a new node to the tree. If the conn_type is the same as the root's
        current connector type, the node is added to the first level.
        Otherwise, the whole tree is pushed down one level and a new root
        connector is created, connecting the existing tree and the new node.
        """
        if len(self.children) < 2:
            self.connector = conn_type
        if self.connector == conn_type:
            if isinstance(node, Node) and (node.connector == conn_type or
                    len(node) == 1):
                self.children.extend(node.children)
            else:
                self.children.append(node)
        else:
            obj = Node(self.children, self.connector, self.negated)
            self.connector = conn_type
            self.children = [obj, node]

    def negate(self):
        """
        Negate the sense of the root connector.

        Interpreting the meaning of this negate is up to client code. This
        method is useful for implementing "not" arrangements.
        """
        self.children = [Node(self.children, self.connector, not self.negated)]
        self.connector = self.default

    def start_subtree(self, conn_type):
        """
        Sets up internal state so that new nodes are added to a subtree of the
        current node. The conn_type specifies how the sub-tree is joined to the
        existing children.
        """
        if len(self.children) == 1:
            self.connector = conn_type
        elif self.connector != conn_type:
            self.children = [Node(self.children, self.connector, self.negated)]
            self.connector = conn_type
            self.negated = False

        self.subtree_parents.append(Node(self.children, self.connector,
                self.negated))
        self.connector = self.default
        self.negated = False
        self.children = []

    def end_subtree(self):
        """
        Closes off the most recently unmatched start_subtree() call.

        This puts the current state into a node of the parent tree and returns
        the current instances state to be the parent.
        """
        obj = self.subtree_parents.pop()
        node = Node(self.children, self.connector)
        self.connector = obj.connector
        self.negated = obj.negated
        self.children = obj.children
        self.children.append(node)
