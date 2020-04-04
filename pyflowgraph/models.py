from __future__ import annotations

import copy
import ast

from log import logger

import vb_utils
from external.gumtree import GumTree


class Node:
    class Property:
        UNMAPPABLE = 'unmappable'
        EXTRA_TOKENS = 'extra-tokens'
        # ORDER = 'order'  # todo

    def set_property(self, prop, value):
        self.data[prop] = value

    def get_property(self, prop, default=None):
        return self.data.get(prop, default)

    class Version:
        BEFORE_CHANGES = 0
        AFTER_CHANGES = 1

    def __init__(self, label, ast, control, key=None, data=None, version=Version.BEFORE_CHANGES):
        global _statement_cnt
        self.statement_num = _statement_cnt
        _statement_cnt += 1

        self.data = data or {}

        self.label = str(label)
        self.ast = ast
        self.key = key
        self.control = control
        self.branch_kind = True

        self.mapped = None

        self.in_edges = set()
        self.out_edges = set()

        self.gt_node = None
        self.is_changed = False
        self.version = version

    def deep_update_data(self, new_data):
        self.data = vb_utils.deep_merge_dict(self.data or {}, new_data)

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
        VARIABLE_DECL = 'variable-decl'
        VARIABLE_USAGE = 'variable-usage'
        LITERAL = 'literal'
        UNDEFINED = 'undefined'

    def __init__(self, label, ast, control, key=None, kind=None):
        super().__init__(label, ast, control, key=key)

        self.kind = kind or self.Kind.UNDEFINED

    def __repr__(self):
        return f'#{self.statement_num} {self.label} <{self.kind}>'


class OperationNode(Node):
    class Label:
        RETURN = 'return'
        CONTINUE = 'continue'
        BREAK = 'break'
        RAISE = 'raise'
        PASS = 'pass'
        ASSIGN = '='

    class Kind:
        COLLECTION = 'collection'
        METHOD_CALL = 'method-call'
        ASSIGN = 'assignment'
        COMPARE = 'comparision'
        RETURN = 'return'
        RAISE = 'raise'
        BREAK = 'break'
        CONTINUE = 'continue'
        SUBSCRIPT_SLICE = 'subscript-slice'
        SUBSCRIPT_INDEX = 'subscript-index'
        UNCLASSIFIED = 'undefined'

    def __init__(self, label, ast, control, key=None, kind=None, branch_kind=None):
        super().__init__(label, ast, control, key=key)
        self.kind = kind or self.Kind.UNCLASSIFIED
        self.branch_kind = branch_kind

        if self.control is not None:
            self.control.create_control_edge(self, branch_kind=branch_kind)

    def __repr__(self):
        return f'#{self.statement_num} {self.label} <{self.kind}> [branch={self.branch_kind}]'


class ControlNode(Node):
    class Label:
        IF = 'if'
        FOR = 'for'
        TRY = 'try'
        EXCEPT = 'except'
        FINALLY = 'finally'

    def __init__(self, label, ast, control, branch_kind=None):
        super().__init__(label, ast, control)
        self.branch_kind = branch_kind

        if self.control is not None:
            self.control.create_control_edge(self, branch_kind=branch_kind)

    def __repr__(self):
        return f'#{self.statement_num} {self.label} [branch={self.branch_kind}]'


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

    # special
    MAP = 'map'
    CONTROL = 'control'

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

        self.changed_nodes = set()

        self.gumtree = None

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
            unresolved_refs = copy.copy(graph.var_refs)  # because we remove from set
            for ref_node in graph.var_refs:
                def_nodes = self.var_key_to_def_nodes.get(ref_node.key)
                if def_nodes:
                    for def_node in def_nodes:
                        def_node.create_edge(ref_node, LinkType.REFERENCE)
                    unresolved_refs.remove(ref_node)

            if op_link_type:
                for op_node in graph.op_nodes:
                    for sink in old_sinks:
                        if not op_node.has_in_edge(sink, op_link_type):
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

    def map_to_gumtree(self, gt):
        self.gumtree = gt

        with open(gt.source_path, 'r+') as f:
            lr = vb_utils.LineReader(''.join(f.readlines()))

        for node in self.nodes:
            if node.get_property(Node.Property.UNMAPPABLE):
                continue

            fst = node.ast.first_token
            lst = node.ast.last_token

            line = fst.start[0]
            col = fst.start[1]

            end_line = lst.end[0]
            end_col = lst.end[1]

            pos = lr.get_pos(line, col) + 2
            length = lr.get_pos(end_line, end_col) - lr.get_pos(line, col)

            type_label = None
            if isinstance(node, DataNode):
                if isinstance(node.ast, ast.Attribute):
                    if node.kind == DataNode.Kind.VARIABLE_USAGE:
                        type_label = GumTree.TypeLabel.ATTRIBUTE_LOAD
                    elif node.kind == DataNode.Kind.VARIABLE_DECL:
                        type_label = GumTree.TypeLabel.ATTRIBUTE_STORE
                elif isinstance(node.ast, ast.arg):
                    if node.kind == DataNode.Kind.VARIABLE_DECL:
                        type_label = GumTree.TypeLabel.SIMPLE_ARG
                else:
                    if node.kind == DataNode.Kind.VARIABLE_USAGE:
                        type_label = GumTree.TypeLabel.NAME_LOAD
                    elif node.kind == DataNode.Kind.VARIABLE_DECL:
                        type_label = GumTree.TypeLabel.NAME_STORE
            elif isinstance(node, OperationNode):
                if node.kind == OperationNode.Kind.ASSIGN:
                    type_label = GumTree.TypeLabel.ASSIGN
                elif node.kind == OperationNode.Kind.METHOD_CALL:
                    type_label = GumTree.TypeLabel.METHOD_CALL

            found = gt.find_node(pos, length, type_label=type_label)
            if found:
                logger.info(f'fg node {node} is mapped to gt node {found}', show_pid=True)

                node.gt_node = found
                found.fg_node = node
            else:
                logger.warning(f'Node {node} is not mapped to any gumtree node', show_pid=True)
                raise GumtreeMappingException

        for node in gt.nodes:
            if not node.fg_node:
                logger.info(f'gt-fg mapping failed for node {node}', show_pid=True)

    @staticmethod
    def map_by_gumtree(fg1, fg2, gt_matches):
        for match in gt_matches:
            gt_src_node = fg1.gumtree.node_id_to_node[int(match.get('src'))]
            gt_dest_node = fg2.gumtree.node_id_to_node[int(match.get('dest'))]

            invalid_mapping = False
            if not gt_src_node.fg_node:
                invalid_mapping = True

            if not gt_dest_node.fg_node:
                invalid_mapping = True

            if invalid_mapping:
                continue

            fg_src_node = gt_src_node.fg_node
            fg_dest_node = gt_dest_node.fg_node

            fg_src_node.mapped = fg_dest_node
            fg_dest_node.mapped = fg_src_node

            fg_src_node.create_edge(fg_dest_node, LinkType.MAP)

    def calc_changed_nodes_by_gumtree(self):
        self.changed_nodes.clear()

        for node in self.nodes:
            if isinstance(node, EntryNode):
                continue

            if node.get_property(Node.Property.UNMAPPABLE):
                continue

            if node.gt_node.is_changed():
                self.changed_nodes.add(node)

                defs = node.get_definitions()
                for d in defs:
                    self.changed_nodes.add(d)

    def find_by_ast(self, ast_node):
        for node in self.nodes:
            if node.ast == ast_node:
                return node
        return None


_statement_cnt = 0


class EntryNodeDuplicated(Exception):  # TODO: move outside of this file
    pass


class GumtreeMappingException(Exception):
    pass
