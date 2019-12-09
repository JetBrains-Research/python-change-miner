from __future__ import annotations

import copy

import vb_utils
from pyflowgraph.build import EntryNodeDuplicated


class Node:
    def __init__(self, label, ast, control, key=None):
        self.label = str(label)
        self.ast = ast
        self.key = key
        self.control = control

        self.in_edges = set()
        self.out_edges = set()

    def is_statement(self):
        return isinstance(self, ControlNode)


class DataNode(Node):
    class Kind:
        FUNCTION = 'function'
        VARIABLE = 'variable'
        LITERAL = 'literal'
        UNDEFINED = 'undefined'

    def __init__(self, label, ast, control, key=None, kind=None):
        super().__init__(label, ast, control, key=key)

        self.kind = kind or self.Kind.UNDEFINED


class OperationNode(Node):
    class Kind:
        COLLECTION = 'collection'
        FUNCTION = 'function'
        ASSIGN = 'assignment'
        COMPARE = 'comparision'
        RETURN = 'return'
        UNCLASSIFIED = 'undefined'

    def __init__(self, label, ast, control, key=None, kind=None, branch_kind=None):
        super().__init__(label, ast, control, key=key)
        self.kind = kind or self.Kind.UNCLASSIFIED

        if self.control is not None:
            ControlEdge(node_from=self.control, node_to=self, branch_kind=branch_kind)


class ControlNode(Node):
    pass


class EntryNode(Node):
    pass


class Edge:
    def __init__(self, label, node_from, node_to):
        self.label = label
        self.node_from = node_from
        self.node_to = node_to

        node_from.out_edges.add(self)
        node_to.in_edges.add(self)


class ControlEdge(Edge):
    def __init__(self, node_from, node_to, branch_kind=True):
        super().__init__('control', node_from, node_to)
        self.branch_kind = branch_kind


class DataEdge(Edge):
    def __init__(self, label, node_from, node_to):
        super().__init__(label, node_from, node_to)


class LinkType:
    DEFINITION = 'def'
    RECEIVER = 'recv'
    REFERENCE = 'ref'
    PARAMETER = 'para'
    CONDITION = 'cond'
    QUALIFIER = 'qual'


class ExtControlFlowGraph:
    def __init__(self, node=None):
        self.entry_node = None
        self.nodes = set()
        self.op_nodes = set()
        self.sinks = set()
        self.var_key_to_def_nodes = {}  # key to set
        self.var_refs = set()

        if node:
            self.nodes.add(node)
            self.sinks.add(node)

            if isinstance(node, OperationNode):
                self.op_nodes.add(node)

    def merge_graph(self, graph):
        self.nodes = self.nodes.union(graph.nodes)
        self.op_nodes = self.op_nodes.union(graph.op_nodes)

        unresolved_refs = copy.copy(graph.var_refs)  # because we remove from set
        for ref in graph.var_refs:
            def_nodes = self.var_key_to_def_nodes.get(ref.key)
            if def_nodes:
                for def_node in def_nodes:
                    DataEdge(LinkType.REFERENCE, node_from=def_node, node_to=ref)
                unresolved_refs.remove(ref)

        self.var_refs = self.var_refs.union(unresolved_refs)
        self._merge_def_nodes(graph)

    def parallel_merge_graphs(self, graphs, op_link_type=None):
        old_sinks = copy.copy(self.sinks)

        for graph in graphs:
            if op_link_type:
                for op_node in graph.op_nodes:
                    for sink in old_sinks:
                        DataEdge(op_link_type, node_from=sink, node_to=op_node)

            self.nodes = self.nodes.union(graph.nodes)
            self.op_nodes = self.op_nodes.union(graph.op_nodes)
            self.sinks = self.sinks.union(graph.sinks)
            self.var_refs = self.var_refs.union(graph.var_refs)
            self._merge_def_nodes(graph)

    def _merge_def_nodes(self, graph):
        vb_utils.deep_merge_dict(self.var_key_to_def_nodes, graph.var_key_to_def_nodes)

    def add_node(self, node: Node, link_type=None, op_link_type=None):
        if link_type:
            for sink in self.sinks:
                DataEdge(link_type, node_from=sink, node_to=node)
            self.sinks.clear()

        self.sinks.add(node)
        self.nodes.add(node)

        if isinstance(node, OperationNode):
            self.op_nodes.add(node)

        if node.key:
            if link_type == LinkType.DEFINITION:
                def_nodes = self.var_key_to_def_nodes.setdefault(node.key, set())
                for def_node in copy.copy(def_nodes):
                    if def_node.key == node.key and def_node.control == node.control:
                        def_nodes.remove(def_node)
                def_nodes.add(node)
                self.var_key_to_def_nodes[node.key] = def_nodes
            else:
                self.var_refs.add(node)

    def set_entry_node(self, entry_node):
        if self.entry_node:
            raise EntryNodeDuplicated

        self.entry_node = entry_node
        self.nodes.add(entry_node)