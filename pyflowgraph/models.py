from __future__ import annotations

import copy

import vb_utils


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

    def change_control(self, new_control, new_branch_kind):
        for e in copy.copy(self.in_edges):
            if isinstance(e, ControlEdge) and e.node_from == self.control:
                self.in_edges.remove(e)
                break

        self.control = new_control
        self.branch_kind = new_branch_kind

        new_control.create_control_edge(self, branch_kind=new_branch_kind)

    def get_definitions(self):
        defs = []
        for e in self.in_edges:
            if isinstance(e, DataEdge) and e.label == LinkType.REFERENCE:
                defs.append(e.node_from)
        return defs

    def create_edge(self, node_to, link_type):
        e = DataEdge(link_type, node_from=self, node_to=node_to)
        self.out_edges.add(e)
        node_to.in_edges.add(e)

    def create_control_edge(self, node_to, branch_kind=True):
        e = ControlEdge(node_from=self, node_to=node_to, branch_kind=branch_kind)
        self.out_edges.add(e)
        node_to.in_edges.add(e)

    def has_in_edge(self, node_from, label):
        for e in self.in_edges:
            if e.node_from == node_from and e.label == label:
                return True
        return False

    def get_incoming_dep_nodes(self):
        deps = []
        for e in self.in_edges:
            if e.label == LinkType.DEPENDENCE:
                deps.append(e.node_from)
        return deps


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
        self.branch_kind = branch_kind

        if self.control is not None:
            self.control.create_control_edge(self, branch_kind=branch_kind)


class ControlNode(Node):
    def __init__(self, label, ast, control, branch_kind=None):
        super().__init__(label, ast, control)
        self.branch_kind = branch_kind

        if self.control is not None:
            self.control.create_control_edge(self, branch_kind=branch_kind)


class EntryNode(ControlNode):
    pass


class Edge:
    def __init__(self, label, node_from, node_to):
        self.label = label
        self.node_from = node_from
        self.node_to = node_to


class ControlEdge(Edge):
    def __init__(self, node_from, node_to, branch_kind=True):
        super().__init__('control', node_from, node_to)
        self.branch_kind = branch_kind


class DataEdge(Edge):
    def __init__(self, label, node_from, node_to):  # FIXME: DO NO CONSIDER LABEL AS LINK_TYPE, DEFINE A NEW INDICATOR
        super().__init__(label, node_from, node_to)


class LinkType:
    DEFINITION = 'def'
    RECEIVER = 'recv'
    REFERENCE = 'ref'
    PARAMETER = 'para'
    CONDITION = 'cond'
    QUALIFIER = 'qual'

    # hidden link types
    DEPENDENCE = 'dep'


class ExtControlFlowGraph:
    def __init__(self, node=None):
        self.entry_node = None
        self.nodes = set()
        self.sinks = set()
        self.var_key_to_def_nodes = {}  # key to set
        self.var_refs = set()

        self.op_nodes = set()
        self.statement_sinks = set()
        self.statement_sources = set()

        if node:
            self.nodes.add(node)
            self.sinks.add(node)

            if node.control:
                self.statement_sinks.add(node)
                self.statement_sources.add(node)

            if isinstance(node, OperationNode):
                self.op_nodes.add(node)

    def merge_graph(self, graph):
        self.nodes = self.nodes.union(graph.nodes)
        self.op_nodes = self.op_nodes.union(graph.op_nodes)

        unresolved_refs = copy.copy(graph.var_refs)  # because we remove from set
        for ref_node in graph.var_refs:
            def_nodes = self.var_key_to_def_nodes.get(ref_node.key)
            if def_nodes:
                for def_node in def_nodes:
                    def_node.create_edge(ref_node, LinkType.REFERENCE)
                unresolved_refs.remove(ref_node)

        for sink in self.statement_sinks:
            for source in graph.statement_sources:
                sink.create_edge(source, link_type=LinkType.DEPENDENCE)

        self.sinks = graph.sinks
        self.statement_sinks = graph.statement_sinks

        self.var_refs = self.var_refs.union(unresolved_refs)
        self._merge_def_nodes(graph)

    def parallel_merge_graphs(self, graphs, op_link_type=None):
        old_sinks = copy.copy(self.sinks)

        for graph in graphs:
            if op_link_type:
                for op_node in graph.op_nodes:
                    for sink in old_sinks:
                        sink.create_edge(op_node, op_link_type)

            self.nodes = self.nodes.union(graph.nodes)
            self.op_nodes = self.op_nodes.union(graph.op_nodes)
            self.sinks = self.sinks.union(graph.sinks)
            self.var_refs = self.var_refs.union(graph.var_refs)

            self.statement_sinks = self.statement_sinks.union(graph.statement_sinks)
            self.statement_sources = self.statement_sources.union(graph.statement_sources)

            self._merge_def_nodes(graph)

    def _merge_def_nodes(self, graph):
        vb_utils.deep_merge_dict(self.var_key_to_def_nodes, graph.var_key_to_def_nodes)

    def add_node(self, node: Node, link_type=None):
        if link_type:
            for sink in self.sinks:
                sink.create_edge(node, link_type)
            self.sinks.clear()

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

        self.sinks.add(node)
        self.nodes.add(node)

        if node.control:
            for sink in self.statement_sinks:
                sink.create_edge(node, link_type=LinkType.DEPENDENCE)

            self.statement_sinks.clear()
            self.statement_sinks.add(node)

            if not self.statement_sources:
                self.statement_sources.add(node)

        if isinstance(node, OperationNode):
            self.op_nodes.add(node)

    def set_entry_node(self, entry_node):
        if self.entry_node:
            raise EntryNodeDuplicated

        self.entry_node = entry_node
        self.nodes.add(entry_node)


class EntryNodeDuplicated(Exception):  # TODO: move outside of this file
    pass
