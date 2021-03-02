import ast
import html
from typing import Dict, Set

from asttokens import asttokens

import settings
from log import logger
from pyflowgraph import models, ast_utils
from pyflowgraph.models import Node, DataNode, OperationNode, ExtControlFlowGraph, ControlNode, DataEdge, LinkType, \
    EntryNode, EmptyNode, ControlEdge, StatementNode

class BuildingContext:
    def __init__(self):
        self.var_key_to_def_nodes: Dict[Set] = {}

    def get_fork(self):
        result = BuildingContext()
        for k, v in self.var_key_to_def_nodes.items():
            result.var_key_to_def_nodes[k] = set().union(v)
        return result

    def add_variable(self, node):
        def_nodes = self.var_key_to_def_nodes.setdefault(node.key, set())
        for def_node in [def_node for def_node in def_nodes if def_node.key == node.key]:
            def_node_stack = def_node.get_property(Node.Property.DEF_CONTROL_BRANCH_STACK)
            node_stack = node.get_property(Node.Property.DEF_CONTROL_BRANCH_STACK)

            if len(def_node_stack) < len(node_stack):
                continue

            if def_node_stack[:len(node_stack)] == node_stack:
                def_nodes.remove(def_node)
        def_nodes.add(node)
        self.var_key_to_def_nodes[node.key] = def_nodes

    def remove_variables(self, control_stack_branch):
        for def_nodes in self.var_key_to_def_nodes.values():
            same_stack_defs = [node for node in def_nodes
                               if node.get_property(Node.Property.DEF_CONTROL_BRANCH_STACK) == control_stack_branch]
            for def_node in same_stack_defs:
                def_nodes.remove(def_node)

    def get_variables(self, var_key):
        return self.var_key_to_def_nodes.get(var_key)


class GraphBuilder:
    def build_from_source(self, source_code, show_dependencies=False, build_closure=True):
        models._statement_cnt = 0
        try:
            source_code_ast = ast.parse(source_code, mode='exec')
            logger.info(f"Parsing completed, code = {source_code}")
        except:
            logger.error(f"Error in parsing, code = {source_code}")
            raise GraphBuildingException

        tokenized_ast = asttokens.ASTTokens(source_code, tree=source_code_ast)

        if isinstance(tokenized_ast.tree, ast.Module) and isinstance(tokenized_ast.tree.body[0], ast.FunctionDef):
            root_ast = tokenized_ast.tree.body[0]
        else:
            root_ast = tokenized_ast.tree

        log_level = settings.get("logger_file_log_level", 'INFO')

        if log_level != 'DEBUG':
            ast_visitor = ASTVisitor()
        else:
            ast_visitor = ASTVisitor_Debug()

        fg = ast_visitor.visit(root_ast)

        if not show_dependencies:
            self.resolve_dependencies(fg)

        if build_closure:
            self.build_closure(fg)

        return fg

    def build_from_file(self, file_path, show_dependencies=False, build_closure=True):
        with open(file_path, 'r+') as f:
            data = f.read()
        return self.build_from_source(data, show_dependencies=show_dependencies, build_closure=build_closure)

    @classmethod
    def _build_data_closure(cls, node, processed_nodes):
        if node.get_definitions():
            return

        for edge in node.in_edges.copy():
            if not isinstance(edge, DataEdge):
                continue

            in_nodes = edge.node_from.get_definitions()
            if not in_nodes:
                in_nodes.add(edge.node_from)
            else:
                for in_node in in_nodes:
                    if not node.has_in_edge(in_node, edge.label):
                        in_node.create_edge(node, edge.label)

            for in_node in in_nodes:
                if in_node not in processed_nodes:
                    cls._build_data_closure(in_node, processed_nodes)

                for in_node_edge in in_node.in_edges:
                    if isinstance(in_node_edge, DataEdge) and not isinstance(in_node_edge.node_from, DataNode):
                        if not in_node_edge.node_from.has_in_edge(node, edge.label):
                            after_in_node = in_node_edge.node_from
                            after_in_node.update_property(
                                Node.Property.DEF_FOR, in_node.get_property(Node.Property.DEF_FOR, []))
                            def_for = after_in_node.get_property(Node.Property.DEF_FOR, [])

                            if edge.label == LinkType.DEFINITION:
                                if not def_for or node.statement_num not in def_for:
                                    continue

                            if not node.has_in_edge(after_in_node, edge.label):
                                after_in_node.create_edge(node, edge.label)

        processed_nodes.add(node)

    @classmethod
    def _build_control_closure(cls, node, processed_nodes):
        if not isinstance(node, ControlNode):
            return

        for in_control in node.get_incoming_nodes(label=LinkType.CONTROL):  # only controls have out control edges now
            if in_control not in processed_nodes:
                cls._build_control_closure(in_control, processed_nodes)

            for e in in_control.in_edges:
                in_control2 = e.node_from
                if not isinstance(e, ControlEdge):
                    continue

                in_control2.create_control_edge(node, e.branch_kind)

        processed_nodes.add(node)

    @classmethod
    def _build_control_data_closure(cls, node, processed_nodes):
        if not isinstance(node, StatementNode):
            return

        logger.debug(f'In node {node}')
        node_controls = {control for (control, branch_kind) in node.control_branch_stack}
        for e in node.in_edges.copy():
            in_node = e.node_from
            if not isinstance(e, ControlEdge) or not isinstance(in_node, ControlNode):  # op nodes processed as in_node2
                continue

            if in_node not in processed_nodes:
                logger.debug(f'Node {in_node} was not visited, going into')
                cls._build_control_data_closure(in_node, processed_nodes)

            visited = set()
            for e2 in in_node.in_edges.copy():
                in_node2 = e2.node_from
                if not isinstance(in_node2, OperationNode) and not isinstance(in_node2, ControlNode):
                    continue
                if in_node2 in visited:
                    continue

                if isinstance(in_node2, ControlNode):
                    if isinstance(node, ControlNode):
                        continue  # the closure is already built

                    lowest_control = in_node2
                else:
                    lowest_control = None  # will be found because the middle node = ControlNode
                    for control in in_node2.get_outgoing_nodes():
                        if not isinstance(control, ControlNode) or control not in node_controls:
                            continue

                        if lowest_control is None or control.statement_num < lowest_control.statement_num:
                            lowest_control = control

                if lowest_control == in_node:
                    branch_kind = e.branch_kind
                else:
                    in_lowest_e = None  # will be found because of control closure made earlier
                    for e3 in lowest_control.out_edges:
                        if e3.label == LinkType.CONTROL and e3.node_to == in_node:
                            in_lowest_e = e3
                            break
                    branch_kind = in_lowest_e.branch_kind

                in_node2.create_control_edge(node, branch_kind, add_to_stack=False)
                logger.debug(f'Created control edge from {in_node2} to {node} with kind = {branch_kind} '
                             f'for node={node}, in_node={in_node}, in_node2={in_node2}')
                visited.add(in_node2)

        processed_nodes.add(node)

    @classmethod
    def _process_fg_nodes(cls, fg, processor_fn):
        logger.debug('-- Starting fg nodes processing --')
        processed_nodes = set()
        for node in fg.nodes:
            if node not in processed_nodes:
                logger.debug(f'Running processor_fn for node {node}')
                processor_fn(node, processed_nodes)

    @classmethod
    def build_closure(cls, fg):
        cls._process_fg_nodes(fg, processor_fn=cls._build_data_closure)
        cls._process_fg_nodes(fg, processor_fn=cls._build_control_closure)
        cls._process_fg_nodes(fg, processor_fn=cls._build_control_data_closure)

    @classmethod
    def _adjust_controls(cls, node, processed_nodes):
        if not isinstance(node, StatementNode):
            return

        in_deps = node.get_incoming_nodes(label=LinkType.DEPENDENCE)
        if not in_deps:
            processed_nodes.add(node)
            return

        control_branch_stacks = []
        control_to_kinds = {}
        for in_dep in in_deps:
            if isinstance(in_dep, ControlNode):
                processed_nodes.add(node)
                return

            if in_dep not in processed_nodes:
                cls._adjust_controls(in_dep, processed_nodes)

            control_branch_stacks.append(in_dep.control_branch_stack)
        control_branch_stacks.append(node.control_branch_stack)

        for stack in control_branch_stacks:
            for control, branch_kind in stack:
                s = control_to_kinds.setdefault(control, set())
                s.add(branch_kind)

        deepest_control = None
        branch_kind = None
        for control, kinds in control_to_kinds.items():
            if len(kinds) == 1:
                if deepest_control is None or deepest_control.statement_num < control.statement_num:
                    deepest_control = control
                    branch_kind = next(iter(kinds))

        if deepest_control:
            node.reset_controls()
            node.control_branch_stack = deepest_control.control_branch_stack.copy()
            deepest_control.create_control_edge(node, branch_kind)
        processed_nodes.add(node)

    @staticmethod
    def _remove_empty_nodes(fg):
        for node in fg.nodes.copy():
            if isinstance(node, EmptyNode):
                fg.remove_node(node)

    @staticmethod
    def _cleanup_deps(fg):
        for node in fg.nodes:
            dep_edges = [e for e in node.in_edges if e.label == LinkType.DEPENDENCE]
            for e in dep_edges:
                node.remove_in_edge(e)

    @classmethod
    def resolve_dependencies(cls, fg):
        cls._process_fg_nodes(fg, processor_fn=cls._adjust_controls)
        cls._remove_empty_nodes(fg)
        cls._cleanup_deps(fg)


class ASTVisitorHelper:
    def __init__(self, ast_visitor):
        self.visitor = ast_visitor

    def create_graph(self):
        return self.visitor.create_graph()

    def _get_assign_group(self, node):
        group = []
        if isinstance(node, ast.Name):
            group.append(node)
        elif isinstance(node, ast.Tuple) or isinstance(node, ast.List):
            for el in node.elts:
                group.extend(self._get_assign_group(el))
        elif isinstance(node, ast.Starred):
            group.append(node.value)
        else:
            logger.error(f'Unsupported node (unable to get assign group) = {node}')
            raise GraphBuildingException(f'Unsupported node (unable to get assign group) = {node}')

        return group

    def get_assign_graph_and_vars(self, op_node, target, prepared_value):
        if isinstance(target, (ast.Name, ast.arg)):
            var_name = ast_utils.get_node_full_name(target)
            var_key = ast_utils.get_node_key(target)

            val_fg = prepared_value
            var_node = DataNode(var_name, target, key=var_key, kind=DataNode.Kind.VARIABLE_DECL)

            sink_nums = []
            for sink in val_fg.sinks:
                sink.update_property(Node.Property.DEF_FOR, [var_node.statement_num])
                sink_nums.append(sink.statement_num)
            var_node.set_property(Node.Property.DEF_BY, sink_nums)

            val_fg.add_node(op_node, link_type=LinkType.PARAMETER)
            val_fg.add_node(var_node, link_type=LinkType.DEFINITION)

            var_node.set_property(Node.Property.DEF_CONTROL_BRANCH_STACK, op_node.control_branch_stack)

            return val_fg, [var_node]

        elif isinstance(target, ast.Attribute):
            var_name = ast_utils.get_node_full_name(target)
            var_key = ast_utils.get_node_key(target)

            val_fg = prepared_value
            var_node = DataNode(var_name, target, key=var_key, kind=DataNode.Kind.VARIABLE_DECL)

            sink_nums = []
            for sink in val_fg.sinks:
                sink.update_property(Node.Property.DEF_FOR, [var_node.statement_num])
                sink_nums.append(sink.statement_num)
            var_node.set_property(Node.Property.DEF_BY, sink_nums)

            val_fg.add_node(op_node, link_type=LinkType.PARAMETER)
            val_fg.add_node(var_node, link_type=LinkType.DEFINITION)

            fg = self.visitor.visit(target.value)
            val_fg.merge_graph(fg)
            for node in fg.nodes:
                node.create_edge(var_node, link_type=LinkType.QUALIFIER)

            return val_fg, [var_node]

        elif isinstance(target, ast.Subscript):
            var_name = ast_utils.get_node_full_name(target)

            val_fg = prepared_value
            var_node = DataNode(var_name, target, kind=DataNode.Kind.VARIABLE_DECL)

            sink_nums = []
            for sink in val_fg.sinks:
                sink.update_property(Node.Property.DEF_FOR, [var_node.statement_num])
                sink_nums.append(sink.statement_num)
            var_node.set_property(Node.Property.DEF_BY, sink_nums)

            val_fg.add_node(op_node, link_type=LinkType.PARAMETER)
            val_fg.add_node(var_node, link_type=LinkType.DEFINITION)

            arr_fg = self.visitor.visit(target.value)
            slice_fg = self.visitor.visit(target.slice)

            val_fg.merge_graph(arr_fg)
            val_fg.merge_graph(slice_fg)

            for node in arr_fg.nodes:
                # node.create_edge(var_node, link_type=LinkType.QUALIFIER)
                node.create_edge(var_node, link_type=LinkType.REFERENCE)
            for node in slice_fg.nodes:
                node.create_edge(var_node, link_type=LinkType.PARAMETER)

            return val_fg, [var_node]

        elif isinstance(target, (ast.Tuple, ast.List)):  # Starred appears inside collections
            vars = []
            if isinstance(prepared_value, ExtControlFlowGraph):  # for function calls TODO: think about tree mapping
                assign_group = self._get_assign_group(target)
                fgs = []

                for el in assign_group:
                    fg, curr_vars = self.get_assign_graph_and_vars(op_node, el, self.create_graph())
                    fgs.append(fg)
                    vars += curr_vars

                prepared_value.parallel_merge_graphs(fgs, op_link_type=LinkType.PARAMETER)
                return prepared_value, vars
            else:
                g = self.create_graph()
                fgs = []
                for i, el in enumerate(target.elts):
                    fg, curr_vars = self.get_assign_graph_and_vars(op_node, el, prepared_value[i])
                    fgs.append(fg)
                    vars += curr_vars
                g.parallel_merge_graphs(fgs)
                return g, vars
        elif isinstance(target, ast.Starred):
            return self.get_assign_graph_and_vars(op_node, target.value, prepared_value)
        else:
            raise GraphBuildingException(f'Unsupported target node = {target}')

    @staticmethod
    def _extract_collection_values(collection):
        if isinstance(collection, ast.Tuple) or isinstance(collection, ast.List):
            return collection.elts
        elif isinstance(collection, ast.Dict):
            return collection.keys
        else:
            logger.error(f'Unable to extract collection values from {collection}')
            raise GraphBuildingException(f'Unable to extract collection values from {collection}')

    def prepare_assign_values(self, target, value):
        """
        target is used for structure definition only
        """
        if isinstance(target, (ast.Name, ast.arg, ast.Attribute, ast.Subscript, ast.Starred, ast.ListComp)):
            return self.visitor.visit(value)
        elif isinstance(target, (ast.Tuple, ast.List)):
            prepared_arr = []
            if isinstance(value, (ast.Call, ast.Name, ast.Attribute)):
                return self.visitor.visit(value)
            else:
                values = self._extract_collection_values(value)
                for i, el in enumerate(target.elts):
                    if isinstance(el, ast.Starred):
                        starred_index = i
                        break
                    prepared_arr.append(self.prepare_assign_values(el, values[i]))
                else:  # no Starred
                    return prepared_arr

                starred_val_cnt = len(values) - len(target.elts) + 1
                starred_val_list = values[starred_index:starred_index + starred_val_cnt]

                if len(starred_val_list) > 0:
                    if isinstance(starred_val_list[0], (list, tuple)):
                        starred_val_list = starred_val_list[0].elts

                starred_fg = self.create_graph()
                starred_fg.parallel_merge_graphs([self.visitor.visit(val) for val in starred_val_list])

                op_node = OperationNode('List', target, self.visitor.control_branch_stack,
                                        kind=OperationNode.Kind.COLLECTION)

                starred_fg.add_node(op_node, link_type=LinkType.PARAMETER)
                prepared_arr.append(starred_fg)

                for i, val in enumerate(values[starred_index + starred_val_cnt:]):
                    prepared_arr.append(self.prepare_assign_values(target.elts[1 + starred_index + i], val))
            return prepared_arr
        else:
            logger.error(f'Unsupported target node = {target}')
            raise GraphBuildingException(f'Unsupported target node = {target}')

    def visit_assign(self, node, targets):
        g = self.create_graph()
        op_node = OperationNode(OperationNode.Label.ASSIGN, node, self.visitor.control_branch_stack,
                                kind=OperationNode.Kind.ASSIGN)
        syntax_left = max([t.last_token.endpos for t in targets])
        syntax_right = node.value.first_token.startpos
        op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [[syntax_left, syntax_right]])

        fgs = []
        assigned_nodes = []
        for target in targets:
            prepared_value = self.prepare_assign_values(target, node.value)
            fg, nodes = self.get_assign_graph_and_vars(op_node, target, prepared_value)
            assigned_nodes += nodes
            fgs.append(fg)

        g.parallel_merge_graphs(fgs)

        for n in assigned_nodes:
            self.visitor.context.add_variable(n)

        return g


class ASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.context_stack = [BuildingContext()]
        self.fg = self.create_graph()

        self.curr_control = None
        self.curr_branch_kind = True
        self.control_branch_stack = []

        self.visitor_helper = ASTVisitorHelper(self)

        self.log_level = settings.get("logger_file_log_level", 'INFO')


    @property
    def context(self):
        return self.context_stack[-1]

    def create_graph(self, node=None):
        return ExtControlFlowGraph(self, node=node)

    def _switch_context(self, new_context):
        self.context_stack.append(new_context)

    def _pop_context(self):
        self.context_stack.pop()

    def _switch_control_branch(self, new_control, new_branch_kind, replace=False):
        if replace:
            self._pop_control_branch()

        self.control_branch_stack.append((new_control, new_branch_kind))

    def _pop_control_branch(self):
        self.curr_control, self.curr_branch_kind = self.control_branch_stack.pop()

    # general AST visits
    def _visit_collection(self, node):
        fg = self.create_graph()
        fg.parallel_merge_graphs([self.visit(item) for item in node.elts])

        op_node = OperationNode(node.__class__.__name__, node, self.control_branch_stack,
                                kind=OperationNode.Kind.COLLECTION)
        op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [
            [node.first_token.startpos, node.first_token.endpos], [node.last_token.startpos, node.last_token.endpos]
        ])
        fg.add_node(op_node, link_type=LinkType.PARAMETER)
        return fg

    def _visit_op(self, op_name, node, op_kind, params, syntax_tokens=None):
        op_node = OperationNode(op_name, node, self.control_branch_stack, kind=op_kind)
        op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [
            [node.first_token.endpos, node.last_token.startpos]
        ])

        last_param = None
        calc_syntax_tokens = []

        param_fgs = []
        for param in params:
            param_fg = self.visit(param)
            param_fg.add_node(op_node, link_type=LinkType.PARAMETER)
            param_fgs.append(param_fg)

            if last_param:
                calc_syntax_tokens.append([last_param.last_token.endpos, param.first_token.startpos])
            last_param = param

        op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, syntax_tokens or calc_syntax_tokens)

        g = self.create_graph()
        g.parallel_merge_graphs(param_fgs)
        return g

    def _visit_bin_op(self, op, left, right, op_name=None, op_kind=OperationNode.Kind.UNCLASSIFIED):
        return self._visit_op(op_name or op.__class__.__name__.lower(), op, op_kind, [left, right])

    def _visit_entry_node(self, node):
        entry_node = EntryNode(node)
        self.fg.set_entry_node(entry_node)
        self._switch_control_branch(entry_node, True)

        arg_fgs = []
        if isinstance(node, ast.FunctionDef):
            arg_fgs = self._visit_fn_def_arguments(node)
        self.fg.parallel_merge_graphs(arg_fgs)

        for st in node.body:
            try:
                fg = self.visit(st)
                logger.info(f"Successfully proceed expr = {st} line = {st.first_token.line}")
            except:
                fg = None

            if not fg:
                err_msg = f'Unable to build pfg for expr = {st}, line = {st.first_token.line} skipping...'
                if isinstance(st, ast.Assign):
                    err_msg += f'Assign error: targets = {st.targets}, values = {st.value}'
                logger.error(err_msg, exc_info=True)
                continue

            self.fg.merge_graph(fg)

        self._pop_control_branch()
        return self.fg

    # Root visits
    def visit_Module(self, node):
        return self._visit_entry_node(node)

    def visit_FunctionDef(self, node):
        if not self.fg.entry_node:
            return self._visit_entry_node(node)
        fg = self._visit_non_assign_var_decl(node)
        var_node = next(iter(fg.nodes))
        var_node.set_property(
            Node.Property.SYNTAX_TOKEN_INTERVALS,
            [[node.first_token.startpos, node.first_token.startpos + len(node.first_token.line.strip())]])
        return fg

    def visit_Expr(self, node):
        return self.visit(node.value)

    # Visit literals, variables and collections
    @staticmethod
    def _clear_literal_label(label):
        label = str(label).encode('unicode_escape').decode()
        label = html.escape(label[:24])
        return label

    def visit_Str(self, node):
        return self.create_graph(node=DataNode(self._clear_literal_label(node.s), node, kind=DataNode.Kind.LITERAL))

    def visit_Num(self, node):
        return self.create_graph(node=DataNode(self._clear_literal_label(node.n), node, kind=DataNode.Kind.LITERAL))

    def visit_NameConstant(self, node):
        return self.create_graph(node=DataNode(self._clear_literal_label(node.value), node, kind=DataNode.Kind.LITERAL))

    def visit_Constant(self, node):
        return self.create_graph(node=DataNode(self._clear_literal_label(node.value), node, kind=DataNode.Kind.LITERAL))

    def visit_Pass(self, node):
        return self.create_graph(node=OperationNode(OperationNode.Label.PASS, node, self.control_branch_stack))

    def visit_Lambda(self, node):
        self._switch_context(self.context.get_fork())

        fg = self.create_graph()
        arg_fgs = self._visit_fn_def_arguments(node)
        fg.parallel_merge_graphs(arg_fgs)

        lambda_node = DataNode(OperationNode.Label.LAMBDA, node)
        lambda_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [[
            node.first_token.startpos, node.first_token.endpos]])

        body_fg = self.visit(node.body)
        fg.merge_graph(body_fg)

        fg.add_node(lambda_node, link_type=LinkType.PARAMETER, clear_sinks=True)

        self._pop_context()
        return fg

    # Visit collections
    def visit_List(self, node):
        return self._visit_collection(node)

    def visit_Tuple(self, node):
        return self._visit_collection(node)

    def visit_Set(self, node):  # e.g. var = {1, 2}
        return self._visit_collection(node)

    def visit_Dict(self, node):
        fg_graphs = []
        for n, key in enumerate(node.keys):
            key_value_fg = self._visit_bin_op(node, key, node.values[n], op_name='Key-Value',
                                              op_kind=OperationNode.Kind.UNCLASSIFIED)
            fg_graphs.append(key_value_fg)

        g = self.create_graph()
        g.parallel_merge_graphs(fg_graphs)
        op_node = OperationNode('Dict', node, self.control_branch_stack, kind=OperationNode.Kind.COLLECTION)
        op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [
            [node.first_token.startpos, node.first_token.endpos],
            [node.last_token.startpos, node.last_token.endpos]])
        g.add_node(op_node, link_type=LinkType.PARAMETER)
        return g

    # Visit atomic nodes
    def _visit_var_usage(self, node):
        var_name = ast_utils.get_node_full_name(node)
        var_key = ast_utils.get_node_key(node)

        g = self.create_graph()
        g.add_node(DataNode(var_name, node, key=var_key, kind=DataNode.Kind.VARIABLE_USAGE))
        return g

    def visit_Name(self, node):
        return self._visit_var_usage(node)

    def visit_Attribute(self, node):
        fg = self.visit(node.value)

        attr_name = ast_utils.get_node_full_name(node)
        attr_key = ast_utils.get_node_key(node) if isinstance(node.ctx, ast.Load) else None

        data_node = DataNode(attr_name, node, kind=DataNode.Kind.VARIABLE_USAGE, key=attr_key)
        data_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [
            [node.last_token.startpos, node.last_token.endpos]])
        fg.add_node(data_node, link_type=LinkType.QUALIFIER, clear_sinks=True)
        return fg

    def visit_Subscript(self, node):
        arr_fg = self.visit(node.value)

        slice_fg = self.visit(node.slice)
        name = ast_utils.get_node_full_name(node)
        slice_node = DataNode(name, node, kind=DataNode.Kind.SUBSCRIPT)
        slice_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [])
        slice_fg.add_node(slice_node, link_type=LinkType.PARAMETER, clear_sinks=True)
        arr_fg.merge_graph(slice_fg, link_node=next(iter(slice_fg.sinks)), link_type=LinkType.REFERENCE)
        return arr_fg

    def visit_Index(self, node):
        return self.visit(node.value)

    def visit_Slice(self, node):
        items = [node.lower, node.step, node.upper]
        fgs = []
        for item in items:
            if not item:
                continue

            fg = self.visit(item)
            fgs.append(fg)

        fg = self.create_graph()
        fg.parallel_merge_graphs(fgs)
        return fg

    def visit_ExtSlice(self, node):
        fgs = []
        for dim in node.dims:
            fgs.append(self.visit(dim))

        fg = self.create_graph()
        fg.parallel_merge_graphs(fgs)
        return fg

    def visit_ListComp(self, node):
        op_node = OperationNode(OperationNode.Label.LISTCOMP, node, self.control_branch_stack,
                                kind=OperationNode.Kind.LISTCOMP)
        op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [
            [node.first_token.endpos, node.last_token.startpos]
        ])
        params_fgs = []

        for generator in node.generators:
            params_fgs.append(self.visit(generator))

        elt_fg = self.visit(node.elt)
        elt_fg.add_node(op_node, link_type=LinkType.PARAMETER)
        params_fgs.append(elt_fg)

        g = self.create_graph()
        g.parallel_merge_graphs(params_fgs)
        return g


    def visit_DictComp(self, node):
        op_node = OperationNode(OperationNode.Label.DICTCOMP, node, self.control_branch_stack,
                                kind=OperationNode.Kind.DICTCOMP)
        op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [
            [node.first_token.endpos, node.last_token.startpos]
        ])
        params_fgs = []

        for generator in node.generators:
            params_fgs.append(self.visit(generator))

        key_fg = self.visit(node.key)
        key_fg.add_node(op_node, link_type=LinkType.PARAMETER)
        params_fgs.append(key_fg)

        value_fg = self.visit(node.value)
        value_fg.add_node(op_node, link_type=LinkType.PARAMETER)
        params_fgs.append(value_fg)

        g = self.create_graph()
        g.parallel_merge_graphs(params_fgs)
        return g


    def visit_GeneratorExp(self, node):
        op_node = OperationNode(OperationNode.Label.GENERATOREXPR, node, self.control_branch_stack,
                                kind=OperationNode.Kind.GENERATOREXPR)
        op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [
            [node.first_token.endpos, node.last_token.startpos]
        ])
        params_fgs = []

        for generator in node.generators:
            params_fgs.append(self.visit(generator))

        elt_fg = self.visit(node.elt)
        elt_fg.add_node(op_node, link_type=LinkType.PARAMETER)
        params_fgs.append(elt_fg)

        g = self.create_graph()
        g.parallel_merge_graphs(params_fgs)
        return g

    def visit_comprehension(self, node):
        params_fgs = []
        op_node = OperationNode(OperationNode.Label.COMPREHENSION, node, self.control_branch_stack,
                                kind=OperationNode.Kind.COMPREHENSION)
        op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [
            [node.first_token.endpos, node.last_token.startpos]])
        iter_fg = self._visit_simple_assign(node.target, node.iter, is_op_unmappable=True)
        iter_fg.add_node(op_node, link_type=LinkType.PARAMETER)
        params_fgs.append(iter_fg)

        if node.ifs:
            for each in node.ifs:
                fg = self.visit(each)
                fg.add_node(op_node, link_type=LinkType.CONDITION)
                params_fgs.append(fg)

        g = self.create_graph()
        g.parallel_merge_graphs(params_fgs)
        return g

    # Visit operations
    def visit_BinOp(self, node):
        return self._visit_bin_op(node, node.left, node.right,
                               op_name=node.op.__class__.__name__.lower(),
                               op_kind=OperationNode.Kind.BINARY)

    def visit_BoolOp(self, node):
        op_name = node.op.__class__.__name__.lower()
        return self._visit_op(op_name, node, OperationNode.Kind.BOOL, node.values)

    def visit_UnaryOp(self, node):
        op_name = node.op.__class__.__name__
        return self._visit_op(op_name, node, OperationNode.Kind.UNARY, [node.operand])

    def visit_Assign(self, node):
        return self.visitor_helper.visit_assign(node, targets=node.targets)

    def visit_AnnAssign(self, node):
        return self.visitor_helper.visit_assign(node, targets=[node.target])

    def _visit_aug_op(self, node, left, right, op_name=None, op_kind=OperationNode.Kind.UNCLASSIFIED):
        return self._visit_op(op_name or node.op.__class__.__name__.lower(), node, op_kind, [left, right])

    def visit_AugAssign(self, node):
        val_fg = self._visit_aug_op(node, node.target, node.value, op_kind=OperationNode.Kind.AUG_ASSIGN)
        return self._visit_simple_assign(node.target, val_fg)

    def _visit_simple_assign(self, target, val, is_op_unmappable=False):
        if not isinstance(val, ExtControlFlowGraph):
            prepared_value = self.visitor_helper.prepare_assign_values(target, val)
        else:
            prepared_value = val

        op_node = OperationNode(OperationNode.Label.ASSIGN, target, self.control_branch_stack,
                                kind=OperationNode.Kind.ASSIGN)

        if is_op_unmappable:
            op_node.set_property(Node.Property.UNMAPPABLE, True)

        fg, vars = self.visitor_helper.get_assign_graph_and_vars(op_node, target, prepared_value)
        for var in vars:
            self.context.add_variable(var)
        return fg

    def _visit_non_assign_var_decl(self, target):
        var_name = ast_utils.get_node_full_name(target)
        var_key = ast_utils.get_node_key(target)

        var_node = DataNode(var_name, target, key=var_key, kind=DataNode.Kind.VARIABLE_DECL)
        fg = self.create_graph(node=var_node)

        var_node.set_property(Node.Property.DEF_CONTROL_BRANCH_STACK, self.control_branch_stack)
        self.context.add_variable(var_node)

        return fg

    def _visit_fn_def_arguments(self, node):
        defaults_cnt = len(node.args.defaults)
        args_cnt = len(node.args.args)

        arg_fgs = []
        for arg_num, arg in enumerate(node.args.args):
            if arg_num < args_cnt - defaults_cnt:
                fg = self._visit_non_assign_var_decl(arg)
                arg_fgs.append(fg)
            else:
                default_arg_num = arg_num - (args_cnt - defaults_cnt)
                fg = self._visit_simple_assign(arg, node.args.defaults[default_arg_num], is_op_unmappable=True)
                arg_fgs.append(fg)

        if not all(arg_fgs):
            logger.warning(f'Unsupported args in func def, skipping them...')
            arg_fgs = [fg for fg in arg_fgs if fg]

        return arg_fgs

    def _visit_fn_arguments(self, node):
        arg_fgs = []
        for arg in node.args:
            fg = self.visit(arg)
            arg_fgs.append(fg)

        for keyword in node.keywords:  # named args
            fg = self.visit(keyword.value)
            if keyword.arg:
                arg_node = DataNode(keyword.arg, keyword, kind=DataNode.Kind.KEYWORD)
                arg_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS,
                                      [[keyword.first_token.startpos, keyword.first_token.endpos]])
                fg.add_node(arg_node)
            arg_fgs.append(fg)

        if not all(arg_fgs):
            logger.warning(f'Func has unsupported args; args={node.args}, kwargs={node.keywords}, skipping them...')
            arg_fgs = [fg for fg in arg_fgs if fg]

        return arg_fgs

    def _visit_func_call(self, node, name, syntax_tokens, /, *, key=None):
        arg_fgs = self._visit_fn_arguments(node)

        fg = self.create_graph()
        fg.parallel_merge_graphs(arg_fgs)

        op_node = OperationNode(name, node, self.control_branch_stack, kind=OperationNode.Kind.FUNC_CALL, key=key)
        op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, syntax_tokens)

        fg.add_node(op_node, link_type=LinkType.PARAMETER, clear_sinks=True)
        return fg

    def visit_Call(self, node):
        name = ast_utils.get_node_short_name(node.func)
        key = ast_utils.get_node_key(node.func)

        if isinstance(node.func, ast.Name):
            syntax_tokens = [[node.func.first_token.startpos, node.func.last_token.endpos]]
            return self._visit_func_call(node, name, syntax_tokens, key=key)
        elif isinstance(node.func, ast.Attribute):
            attr_fg = self.visit(node.func)

            syntax_tokens = [[node.func.last_token.startpos, node.func.last_token.endpos]]
            call_fg = self._visit_func_call(node, name, syntax_tokens)

            attr_fg.merge_graph(call_fg, link_node=next(iter(call_fg.sinks)), link_type=LinkType.RECEIVER)
            return attr_fg
        elif isinstance(node.func, ast.Call):
            return self.visit_Call(node.func)
        else:
            logger.error(
                f"Fail in visited node = {node}, unsupported func type = {node.func} line = {node.first_token.line}")
            return None

    # Control statement visits
    def visit_If(self, node):
        control_node = ControlNode(ControlNode.Label.IF, node, self.control_branch_stack)
        control_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS,
                                  [[node.first_token.startpos, node.first_token.endpos]])

        fg = self.visit(node.test)
        fg.add_node(control_node, link_type=LinkType.CONDITION)

        fg_if = self._visit_control_node_body(control_node, node.body, True)
        fg_else = self._visit_control_node_body(control_node, node.orelse, False)
        fg.parallel_merge_graphs([fg_if, fg_else])
        return fg

    def visit_IfExp(self, node):
        line_to_log = node.first_token.line
        if hasattr(node, 'body') and isinstance(node.body, list):
            for expr in node.body:
                line_to_log += expr.first_token.line
        logger.error(f"Failed visited node = {node}, line = {line_to_log}")
        return None


    def visit_For(self, node):
        control_node = ControlNode(ControlNode.Label.FOR, node, self.control_branch_stack)
        control_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS,
                                  [[node.first_token.startpos, node.first_token.endpos]])
        fg = self._visit_simple_assign(node.target, node.iter, is_op_unmappable=True)
        fg.add_node(control_node, link_type=LinkType.CONDITION)

        fg_for = self._visit_control_node_body(control_node, node.body, True)
        fg_else = self._visit_control_node_body(control_node, node.orelse, False)
        fg.parallel_merge_graphs([fg_for, fg_else])
        fg.statement_sinks.clear()
        return fg

    def visit_While(self, node):
        control_node = ControlNode(ControlNode.Label.WHILE, node, self.control_branch_stack)
        control_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS,
                                  [[node.first_token.startpos, node.first_token.endpos]])
        fg = self.visit(node.test)
        fg.add_node(control_node, link_type=LinkType.CONDITION)

        fg1 = self._visit_control_node_body(control_node, node.body, True)
        fg2 = self._visit_control_node_body(control_node, node.orelse, False)
        fg.parallel_merge_graphs([fg1, fg2])
        fg.statement_sinks.clear()
        return fg

    def visit_Try(self, node):
        control_node = ControlNode(ControlNode.Label.TRY, node, self.control_branch_stack)
        control_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS,
                                  [[node.first_token.startpos, node.first_token.endpos]])

        fg = self.create_graph()
        fg.add_node(control_node, link_type=LinkType.CONDITION)

        fg_try = self._visit_control_node_body(control_node, node.body, True)
        fg_else = self._visit_control_node_body(control_node, node.orelse, True)
        fg_finally = self._visit_control_node_body(control_node, node.finalbody, True) #todo add finally in except branch

        self._switch_control_branch(control_node, False)
        handlers_fgs = []
        for handler in node.handlers:
            handler_fg = self.visit(handler)
            handlers_fgs.append(handler_fg)

        fg.parallel_merge_graphs([fg_try, fg_else, fg_finally] + handlers_fgs)

        self._pop_control_branch()
        fg.statement_sinks.clear()
        return fg

    def visit_ExceptHandler(self, node):
        control_node = ControlNode(ControlNode.Label.EXCEPT, node, self.control_branch_stack)
        control_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS,
                                  [[node.first_token.startpos, node.first_token.endpos]])

        fg = self.visit(node.type) if node.type else self.create_graph()
        fg.add_node(control_node, link_type=LinkType.PARAMETER)
        fg.merge_graph(self._visit_control_node_body(control_node, node.body, True))
        fg.statement_sources.clear()  # todo: bad workaround
        return fg

    def visit_Assert(self, node):
        control_node = ControlNode(ControlNode.Label.ASSERT, node, self.control_branch_stack)
        control_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS,
                                  [[node.first_token.startpos, node.first_token.endpos]])
        fg = self.visit(node.test)
        fg.add_node(control_node, link_type=LinkType.CONDITION)

        if node.msg:
            fg_msg = self.visit(node.msg) if node.msg else self.create_graph()
            fg_msg.add_node(control_node, link_type=LinkType.PARAMETER)
            fg.merge_graph(fg_msg, link_node=control_node)

        self._switch_control_branch(control_node, True)
        return fg

    def _visit_control_node_body(self, control_node, statements, new_branch_kind, replace_control=False):
        self._switch_control_branch(control_node, new_branch_kind, replace=replace_control)
        fg = self.create_graph()
        fg.add_node(EmptyNode(self.control_branch_stack))
        for st in statements:
            try:
                st_fg = self.visit(st)
                logger.info(f"Successfully proceed expr = {st} line = {st.first_token.line}")
            except:
                st_fg = None

            if not st_fg:
                err_msg = f'Unable to build pfg for expr = {st}, line = {st.first_token.line} skipping...'
                if isinstance(st, ast.Assign):
                    err_msg += f'Assign error: targets = {st.targets}, values = {st.value}'
                logger.error(err_msg, exc_info=True)
                continue

            fg.merge_graph(st_fg)
        self._pop_control_branch()
        return fg

    def _visit_sub_if_expr(self, control_node, statements, new_branch_kind, replace_control=False):
        self._switch_control_branch(control_node, new_branch_kind, replace=replace_control)
        fg = self.create_graph()
        fg.add_node(EmptyNode(self.control_branch_stack))
        st_fg = self.visit(statements)
        fg.merge_graph(st_fg)
        self._pop_control_branch()
        return fg

    def visit_Import(self, _):
        return self.create_graph()  # TODO: Import.names[i].name <- alias.name, should be able to ref as data node

    def visit_ImportFrom(self, _):
        return self.create_graph()  # TODO:ImportFrom.module -qual> ImportFrom.names[i].name <- alias.name

    # Return/continue/break
    def _visit_dep_resetter(self, label, node, kind, reset_variables=False):
        g = self.create_graph()
        if getattr(node, 'value', None):
            g.merge_graph(self.visit(node.value))
        elif getattr(node, 'exc', None):
            g.merge_graph(self.visit(node.exc))

        op_node = OperationNode(label, node, self.control_branch_stack, kind=kind)
        op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [
            [node.first_token.startpos, node.first_token.endpos]])

        g.add_node(op_node, link_type=LinkType.PARAMETER)

        g.statement_sinks.clear()
        if reset_variables:
            self.context.remove_variables(self.control_branch_stack)

        return g

    def visit_Raise(self, node):
        return self._visit_dep_resetter(OperationNode.Label.RAISE, node, OperationNode.Kind.RAISE, reset_variables=True)

    def visit_Return(self, node):
        return self._visit_dep_resetter(OperationNode.Label.RETURN, node, OperationNode.Kind.RETURN,
                                        reset_variables=True)

    def visit_Continue(self, node):
        return self._visit_dep_resetter(OperationNode.Label.CONTINUE, node, OperationNode.Kind.CONTINUE)

    def visit_Break(self, node):
        return self._visit_dep_resetter(OperationNode.Label.BREAK, node, OperationNode.Kind.BREAK)

    # Other visits

    def visit_Await(self, node):
        return self.visit(node.value)

    def visit_FormattedValue(self, node):
        return self.visit(node.value)

    def visit_JoinedStr(self, node):
        g = self.create_graph()
        g.parallel_merge_graphs([self.visit(val) for val in node.values])

        op_node = OperationNode('fstr', node, self.control_branch_stack, kind=OperationNode.Kind.UNCLASSIFIED)
        g.add_node(op_node, link_type=LinkType.PARAMETER)
        return g

    def visit_Compare(self, node):
        g = None
        last_fg = self.visit(node.left)
        last_ast = node.left
        for i, cmp in enumerate(node.comparators):
            op_node = OperationNode(node.ops[i].__class__.__name__, node, self.control_branch_stack,
                                    kind=OperationNode.Kind.COMPARE)
            syntax_left = last_ast.last_token.endpos
            syntax_right = cmp.first_token.startpos
            op_node.set_property(Node.Property.SYNTAX_TOKEN_INTERVALS, [[syntax_left, syntax_right]])
            right_fg = self.visit(cmp)

            last_fg.add_node(op_node, link_type=LinkType.PARAMETER)
            right_fg.add_node(op_node, link_type=LinkType.PARAMETER)

            fgs = [last_fg, right_fg]
            g = self.create_graph()
            g.parallel_merge_graphs(fgs)

            last_fg = g
            last_ast = cmp
        return g


class ASTVisitorDebug(ASTVisitor):

    def visit(self, node):
        """Visit a node."""
        method = 'visit_' + node.__class__.__name__
        visitor = getattr(self, method, self.generic_visit)
        line_to_log = node.first_token.line
        if hasattr(node, 'body') and isinstance(node.body, list):
            for expr in node.body:
                line_to_log += expr.first_token.line
        try:
            result = visitor(node)
            logger.debug(f"Successfully visited node = {node}, line = {line_to_log}")
            return result
        except:
            logger.error(f"Failed visited node = {node}, line = {line_to_log}")
            return None


class GraphBuildingException(Exception):
    pass
