import ast
import copy

from asttokens import asttokens

from log import logger
from pyflowgraph import models, ast_utils
from pyflowgraph.models import Node, DataNode, OperationNode, ExtControlFlowGraph, ControlNode, DataEdge, LinkType, \
    EntryNode, \
    ControlEdge


class BuildingContext:
    def __init__(self):
        self.local_variables = []
        self.controls = []

    def add_scope(self):
        self.local_variables.append({})

    def remove_scope(self):
        self.local_variables.pop()

    def add_variable(self, node):
        var_id = ast_utils.get_var_full_name(node)
        self.local_variables[-1][var_id] = {
            'id': var_id,
            'ast': node
        }

    def get_variable_info(self, var_id):
        for local_variables in self.local_variables:
            var = local_variables.get(var_id)
            if var is not None:
                return var


class GraphBuilder:
    def __init__(self):
        self.ast_visitor = None

    def build_from_source(self, source_code, show_dependencies=False, build_closure=True):
        models._statement_cnt = 0

        source_code_ast = ast.parse(source_code, mode='exec')
        tokenized_ast = asttokens.ASTTokens(source_code, tree=source_code_ast)

        if isinstance(tokenized_ast.tree, ast.Module) and isinstance(tokenized_ast.tree.body[0], ast.FunctionDef):
            root_ast = tokenized_ast.tree.body[0]
        else:
            root_ast = tokenized_ast.tree

        self.ast_visitor = ASTVisitor()
        fg = self.ast_visitor.visit(root_ast)

        if not show_dependencies:
            self._clean_dependencies(fg)

        if build_closure:
            self.build_closure(fg)

        return fg

    def build_from_file(self, file_path, show_dependencies=False, build_closure=True):
        with open(file_path, 'r+') as f:
            data = f.read()
        return self.build_from_source(data, show_dependencies=show_dependencies, build_closure=build_closure)

    def _build_data_closure(self, node, processed_nodes):
        if node.get_definitions():
            return

        for edge in copy.copy(node.in_edges):
            if not isinstance(edge, DataEdge):
                continue

            in_nodes = edge.node_from.get_definitions()
            if not in_nodes:
                in_nodes.append(edge.node_from)
            else:
                for in_node in in_nodes:
                    if not node.has_in_edge(in_node, edge.label):
                        in_node.create_edge(node, edge.label)

            for in_node in in_nodes:
                if in_node not in processed_nodes:
                    self._build_data_closure(in_node, processed_nodes)

                for in_node_edge in in_node.in_edges:
                    if isinstance(in_node_edge, DataEdge) and not isinstance(in_node_edge.node_from, DataNode):
                        if not in_node_edge.node_from.has_in_edge(node, edge.label):
                            after_in_node = in_node_edge.node_from
                            after_in_node.deep_update_data({'def_for': in_node.data.get('def_for', [])})
                            def_for = after_in_node.data.get('def_for', [])

                            if edge.label == LinkType.DEFINITION:
                                if not def_for or node.statement_num not in def_for:
                                    continue

                            if not node.has_in_edge(after_in_node, edge.label):
                                after_in_node.create_edge(node, edge.label)

        processed_nodes.add(node)

    def _build_control_closure(self, node, processed_nodes):
        for e in copy.copy(node.in_edges):
            if isinstance(e, ControlEdge):
                control_node = e.node_from
                if control_node not in processed_nodes:
                    self._build_control_closure(control_node, processed_nodes)

                for e2 in control_node.in_edges:
                    if isinstance(node, OperationNode) or isinstance(node, ControlNode) \
                            and not node.has_in_edge(e2.node_from, e2.label):
                        e2.node_from.create_control_edge(node, branch_kind=node.branch_kind)
        processed_nodes.add(node)

    def build_closure(self, fg):
        processed_nodes = set()
        for node in fg.nodes:
            if node not in processed_nodes:
                self._build_data_closure(node, processed_nodes)

        processed_nodes.clear()
        for node in fg.nodes:
            if node not in processed_nodes:
                self._build_control_closure(node, processed_nodes)

    @staticmethod
    def _adjust_controls(fg):
        # resolving dependencies for inner nodes in controls
        for control_node in fg.nodes:
            if control_node.label in [ControlNode.Label.IF, ControlNode.Label.FOR, ControlNode.Label.TRY]:  # todo: use kind, not label
                for out_dep_edge in copy.copy(control_node.out_edges):
                    if out_dep_edge.label != LinkType.DEPENDENCE:
                        continue

                    dep_node = out_dep_edge.node_to

                    branch_to_dep_status = {}
                    curr_control_dep_edges = []

                    for e in dep_node.in_edges:
                        if e.label == LinkType.DEPENDENCE and e.node_from.control == control_node:
                            curr_control_dep_edges.append(e)
                            branch_to_dep_status[e.node_from.branch_kind] = True

                    for branch_kind in [True, False]:
                        if branch_to_dep_status.get(branch_kind) and not branch_to_dep_status.get(not branch_kind):
                            dep_node.change_control(control_node, new_branch_kind=branch_kind)
                            break

                    for e in curr_control_dep_edges:
                        dep_node.in_edges.discard(e)
                    dep_node.in_edges.discard(out_dep_edge)

        # adjust other dep edges
        for node in fg.nodes:
            for edge in copy.copy(node.in_edges):
                if edge.label == LinkType.DEPENDENCE:
                    if edge.node_from.control != node.control and not isinstance(edge.node_from, ControlNode):
                        node.change_control(edge.node_from.control, edge.node_from.branch_kind)
                    node.in_edges.remove(edge)

    def _clean_dependencies(self, fg):
        self._adjust_controls(fg)


class ASTVisitorHelper:
    def __init__(self, ast_visitor):
        self.visitor = ast_visitor

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
            raise GraphBuildingException
        return group

    def get_assign_graph_and_vars(self, op_node, target, prepared_value):
        if isinstance(target, ast.Name) or isinstance(target, ast.Attribute) or isinstance(target, ast.arg):
            var_id = ast_utils.get_var_full_name(target)
            var_label = ast_utils.get_var_short_name(target)

            val_fg = prepared_value
            var_node = DataNode(var_label, target, None, var_id, kind=DataNode.Kind.VARIABLE_DECL)

            for sink in val_fg.sinks:
                sink.deep_update_data({'def_for': [var_node.statement_num]})
            var_node.deep_update_data({'def_by': [n.statement_num for n in val_fg.sinks]})

            val_fg.add_node(op_node, LinkType.PARAMETER)
            val_fg.add_node(var_node, LinkType.DEFINITION)
            return val_fg, [target]
        elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):  # Starred appears inside collections
            vars = []
            if isinstance(prepared_value, ExtControlFlowGraph):  # for function calls TODO: think about tree mapping
                assign_group = self._get_assign_group(target)
                fgs = []

                for el in assign_group:
                    fg, curr_vars = self.get_assign_graph_and_vars(op_node, el, ExtControlFlowGraph())
                    fgs.append(fg)
                    vars += curr_vars

                prepared_value.parallel_merge_graphs(fgs, op_link_type=LinkType.PARAMETER)
                return prepared_value, vars
            else:
                g = ExtControlFlowGraph()
                fgs = []
                for i, el in enumerate(target.elts):
                    fg, curr_vars = self.get_assign_graph_and_vars(op_node, el, prepared_value[i])
                    fgs.append(fg)
                    vars += curr_vars
                g.parallel_merge_graphs(fgs)
                return g, vars
        elif isinstance(target, ast.Starred):
            return self.get_assign_graph_and_vars(op_node, target.value, prepared_value)

    def _extract_collection_values(self, value):
        if isinstance(value, ast.Tuple) or isinstance(value, ast.List):
            return value.elts
        elif isinstance(value, ast.Dict):
            return value.keys
        else:
            raise GraphBuildingException

    def prepare_assign_values(self, target, value):
        """
        target is used for structure definition only
        """
        if isinstance(target, ast.Name) or isinstance(target, ast.Attribute) or isinstance(target, ast.arg):
            return self.visitor.visit(value)
        elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
            prepared_arr = []
            if isinstance(value, ast.Call):
                return self.visitor.visit(value)
            elif isinstance(value, ast.Name):
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
                    if isinstance(starred_val_list[0], list) or isinstance(starred_val_list[0], tuple):
                        starred_val_list = starred_val_list[0].elts

                starred_fg = ExtControlFlowGraph()
                starred_fg.parallel_merge_graphs([self.visitor.visit(val) for val in starred_val_list])
                op_node = OperationNode('List', target, kind=OperationNode.Kind.COLLECTION,
                                        control=self.visitor.curr_control, branch_kind=self.visitor.curr_branch_kind)
                starred_fg.add_node(op_node, LinkType.PARAMETER)
                prepared_arr.append(starred_fg)

                for i, val in enumerate(values[starred_index + starred_val_cnt:]):
                    prepared_arr.append(self.prepare_assign_values(target.elts[1 + starred_index + i], val))
            return prepared_arr
        else:
            logger.warning(f'Unknown node type = {target}')
            raise GraphBuildingException

    def visit_assign(self, node):  # TODO: refactoring is needed
        """
        possible targets are Attribute-, Subscript-, Slicing-, Starred+, Name+, List+, Tuple+
        """
        g = ExtControlFlowGraph()
        op_node = OperationNode(OperationNode.Label.ASSIGN, node, kind=OperationNode.Kind.ASSIGN,
                                control=self.visitor.curr_control, branch_kind=self.visitor.curr_branch_kind)
        fgs = []
        assigned_nodes = []
        for target in node.targets:
            prepared_value = self.prepare_assign_values(target, node.value)
            fg, nodes = self.get_assign_graph_and_vars(op_node, target, prepared_value)
            assigned_nodes += nodes
            fgs.append(fg)

        g.parallel_merge_graphs(fgs)

        for node in assigned_nodes:
            self.visitor.context.add_variable(node)

        return g


class ASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.context = BuildingContext()
        self.fg = ExtControlFlowGraph()
        self.curr_control = None
        self.curr_branch_kind = True

        self.control_branch_stack = []
        self.visitor_helper = ASTVisitorHelper(self)

    def _switch_control_branch(self, new_control, new_branch_kind, replace=False):
        old_control = self.curr_control
        old_branch_kind = self.curr_branch_kind
        self.curr_control = new_control
        self.curr_branch_kind = new_branch_kind
        if not replace:
            self.control_branch_stack.append((old_control, old_branch_kind))

    def _pop_control_branch(self):
        self.curr_control, self.curr_branch_kind = self.control_branch_stack.pop()

    # general AST visits
    def _visit_collection(self, node):
        fg = ExtControlFlowGraph()
        fg.parallel_merge_graphs([self.visit(item) for item in node.elts])

        op_node = OperationNode(node.__class__.__name__, node, kind=OperationNode.Kind.COLLECTION,
                                control=self.curr_control, branch_kind=self.curr_branch_kind)
        fg.add_node(op_node, LinkType.PARAMETER)
        return fg

    def _visit_op(self, op_name, op, op_kind, params):
        op_node = OperationNode(op_name, op, kind=op_kind,
                                control=self.curr_control, branch_kind=self.curr_branch_kind)

        param_fgs = []
        for param in params:
            param_fg = self.visit(param)
            param_fg.add_node(op_node, LinkType.PARAMETER)
            param_fgs.append(param_fg)

        g = ExtControlFlowGraph()
        g.parallel_merge_graphs(param_fgs)
        return g

    def _visit_bin_op(self, op, left, right, op_name=None, op_kind=OperationNode.Kind.UNCLASSIFIED):
        return self._visit_op(op_name or op.__class__.__name__.lower(), op, op_kind, [left, right])

    def _visit_entry_node(self, node):
        self.context.add_scope()

        arg_fgs = []
        if isinstance(node, ast.FunctionDef):
            arg_fgs = self._visit_fn_def_arguments(node)
        self.fg.parallel_merge_graphs(arg_fgs)

        entry_node = EntryNode('START', node, control=None)
        self.fg.set_entry_node(entry_node)
        self._switch_control_branch(entry_node, True)

        for st in node.body:
            fg = self.visit(st)
            if fg:
                self.fg.merge_graph(fg)
        self.context.remove_scope()
        return self.fg

    # Root visits
    def visit_Module(self, node):
        return self._visit_entry_node(node)

    def visit_FunctionDef(self, node):
        if not self.fg.entry_node:
            return self._visit_entry_node(node)
        return None

    def visit_Expr(self, node):
        return self.visit(node.value)

    # Visit literals, variables and collections
    def visit_Str(self, node):
        return ExtControlFlowGraph(node=DataNode(node.s, node, None, kind=DataNode.Kind.LITERAL))

    def visit_Num(self, node):
        return ExtControlFlowGraph(node=DataNode(node.n, node, None, kind=DataNode.Kind.LITERAL))

    def visit_NameConstant(self, node):
        return ExtControlFlowGraph(node=DataNode(node.value, node, None, kind=DataNode.Kind.LITERAL))

    def visit_Constant(self, node):
        return ExtControlFlowGraph(node=DataNode(node.value, node, None, kind=DataNode.Kind.LITERAL))

    def visit_Pass(self, node):
        return ExtControlFlowGraph(node=OperationNode(OperationNode.Label.PASS, node,
                                                      control=self.curr_control,
                                                      branch_kind=self.curr_branch_kind))

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

        g = ExtControlFlowGraph()
        g.parallel_merge_graphs(fg_graphs)
        op_node = OperationNode('Dict', node, kind=OperationNode.Kind.COLLECTION,
                                control=self.curr_control, branch_kind=self.curr_branch_kind)
        g.add_node(op_node, LinkType.PARAMETER)
        return g

    # Visit atomic nodes
    def _visit_var_usage(self, node):
        var_id = ast_utils.get_var_full_name(node)
        var_label = ast_utils.get_var_short_name(node)

        g = ExtControlFlowGraph()
        g.add_node(node=DataNode(var_label, node, None, key=var_id, kind=DataNode.Kind.VARIABLE_USAGE))
        return g

    def visit_Name(self, node):
        return self._visit_var_usage(node)

    def visit_Attribute(self, node):
        return self._visit_var_usage(node)

    def visit_Subscript(self, node):
        if isinstance(node.slice, ast.Slice):
            keys = ['lower', 'step', 'upper']
            params = []
            for k in keys:
                attr = getattr(node.slice, k, None)
                if attr:
                    params.append(attr)
            return self._visit_op('[]', node, OperationNode.Kind.SUBSCRIPT_SLICE, params)
        elif isinstance(node.slice, ast.Index):
            return self._visit_op('[]', node, OperationNode.Kind.SUBSCRIPT_INDEX, [node.slice.value])

    # Visit operations
    def visit_BinOp(self, node):
        return self._visit_bin_op(node, node.left, node.right, op_name=node.op.__class__.__name__.lower())

    def visit_BoolOp(self, node):
        op_name = node.op.__class__.__name__.lower()
        return self._visit_op(op_name, node, OperationNode.Kind.UNCLASSIFIED, node.values)

    def visit_UnaryOp(self, node):
        op_name = node.op.__class__.__name__
        return self._visit_op(op_name, node, OperationNode.Kind.UNCLASSIFIED, [node.operand])

    def visit_Assign(self, node):
        return self.visitor_helper.visit_assign(node)

    def _visit_simple_assign(self, target, val, is_op_unmappable=False):
        prepared_value = self.visitor_helper.prepare_assign_values(target, val)
        op_node = OperationNode(OperationNode.Label.ASSIGN, target, kind=OperationNode.Kind.ASSIGN,
                                control=self.curr_control, branch_kind=self.curr_branch_kind)

        if is_op_unmappable:
            op_node.set_property(Node.Property.UNMAPPABLE, True)

        fg, vars = self.visitor_helper.get_assign_graph_and_vars(op_node, target, prepared_value)
        for var in vars:
            self.context.add_variable(var)

        return fg

    def visit_AugAssign(self, node):  # TODO: incorrect
        if isinstance(node.target, ast.Name):
            fg, _ = self.visitor_helper.get_assign_graph_and_vars(
                node, node.target, self._visit_bin_op(node.op, node.target, node.value))
            self.context.add_variable(node.target)
            return fg
        else:
            raise GraphBuildingException

    def visit_AnnAssign(self, node):  # TODO: incorrect
        return GraphBuildingException

        if not node.value:
            return ExtControlFlowGraph()

        prepared_value = self.visitor_helper.prepare_assign_values(node.target, node.value)
        fg, vars = self.visitor_helper.get_assign_graph_and_vars(node, node.target, prepared_value)
        for var in vars:
            id, node = var
            self.context.add_variable(node)

        return fg

    def _visit_method_call(self, node, name):
        arg_fgs = self._visit_fn_arguments(node)

        g = ExtControlFlowGraph()
        g.parallel_merge_graphs(arg_fgs)
        op_node = OperationNode(name, node, kind=OperationNode.Kind.METHOD_CALL,
                                control=self.curr_control, branch_kind=self.curr_branch_kind)
        g.add_node(op_node, LinkType.PARAMETER)
        return g

    def _visit_fn_arguments(self, node):
        arg_fgs = []
        for arg in node.args:
            fg = self.visit(arg)
            arg_fgs.append(fg)

        for keyword in node.keywords:  # named args
            fg = self.visit(keyword.value)
            fg.add_node(DataNode(keyword.arg, keyword, None, kind=DataNode.Kind.LITERAL))
            arg_fgs.append(fg)

        if not all(arg_fgs):
            logger.warning(f'Unable to build flow graph for func, args={node.args}, kwargs={node.keywords}')
            raise GraphBuildingException

        return arg_fgs

    def _visit_fn_def_arguments(self, node):
        defaults_cnt = len(node.args.defaults)
        args_cnt = len(node.args.args)

        arg_fgs = []
        for arg_num, arg in enumerate(node.args.args):
            if arg_num < args_cnt - defaults_cnt:
                var_id = ast_utils.get_var_full_name(arg)
                var_label = ast_utils.get_var_short_name(arg)

                fg = ExtControlFlowGraph()
                arg_node = DataNode(var_label, arg, None, var_id, kind=DataNode.Kind.VARIABLE_DECL)
                fg.add_node(arg_node, link_type=LinkType.DEFINITION)
                arg_fgs.append(fg)
            else:
                default_arg_num = arg_num - (args_cnt - defaults_cnt)
                fg = self._visit_simple_assign(arg, node.args.defaults[default_arg_num], is_op_unmappable=True)
                arg_fgs.append(fg)

        if not all(arg_fgs):
            logger.warning(f'Unable to build flow graph for func def')
            raise GraphBuildingException

        return arg_fgs

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            return self._visit_method_call(node, node.func.id)
        elif isinstance(node.func, ast.Attribute):
            return self._visit_method_call(node, node.func.attr)
        else:
            raise NotImplementedError

    # Control statement visits
    def _switch_control_node(self, visit_func, node, control_node, branch_kind):
        old_control = self.curr_control
        old_branch_kind = self.curr_branch_kind
        self.curr_control = control_node
        self.curr_branch_kind = branch_kind

        visit_func(node)

        self.curr_control = old_control
        self.curr_branch_kind = old_branch_kind

    def visit_If(self, node):
        control_node = ControlNode(ControlNode.Label.IF, node, self.curr_control, branch_kind=self.curr_branch_kind)
        fg = self.visit(node.test)
        fg.add_node(control_node, LinkType.CONDITION)

        fg1 = self._visit_control_node(control_node, node.body, True)
        fg2 = self._visit_control_node(control_node, node.orelse, False)
        fg.parallel_merge_graphs([fg1, fg2])
        return fg

    def visit_For(self, node):
        control_node = ControlNode(ControlNode.Label.FOR, node, self.curr_control, branch_kind=self.curr_branch_kind)
        fg = self._visit_simple_assign(node.target, node.iter, is_op_unmappable=True)
        fg.add_node(control_node, link_type=LinkType.CONDITION)

        fg1 = self._visit_control_node(control_node, node.body, True)
        fg2 = self._visit_control_node(control_node, node.orelse, False)
        fg.parallel_merge_graphs([fg1, fg2])
        return fg

    def visit_Try(self, node):  # todo: finally, else?
        control_node = ControlNode(ControlNode.Label.TRY, node, self.curr_control, branch_kind=self.curr_branch_kind)
        fg = ExtControlFlowGraph()
        fg.add_node(control_node, link_type=LinkType.CONDITION)

        fg1 = self._visit_control_node(control_node, node.body, True)
        self._switch_control_branch(control_node, False)
        handlers_fgs = []
        for handler in node.handlers:
            handler_fg = self.visit(handler)
            handlers_fgs.append(handler_fg)
        fg.parallel_merge_graphs([fg1] + handlers_fgs)
        self._pop_control_branch()
        return fg

    def visit_ExceptHandler(self, node):
        control_node = ControlNode(ControlNode.Label.EXCEPT, node, self.curr_control, branch_kind=self.curr_branch_kind)
        fg = self.visit(node.type) if node.type else ExtControlFlowGraph()
        fg.add_node(control_node, link_type=LinkType.PARAMETER)
        fg.merge_graph(self._visit_control_node(control_node, node.body, True))
        fg.statement_sources.clear()  # todo: bad workaround
        return fg

    def _visit_control_node(self, control_node, statements, new_branch_kind, replace_control=False):
        self._switch_control_branch(control_node, new_branch_kind, replace=replace_control)
        fg = ExtControlFlowGraph()
        for st in statements:
            fg.merge_graph(self.visit(st))
        self._pop_control_branch()
        return fg

    def visit_Import(self, _):
        return ExtControlFlowGraph()  # TODO: Import.names[i].name <- alias.name, should be able to ref as data node

    def visit_ImportFrom(self, _):
        return ExtControlFlowGraph()  # TODO:ImportFrom.module -qual> ImportFrom.names[i].name <- alias.name

    # Return/continue/break
    def _visit_dep_resetter(self, label, ast, kind):
        g = ExtControlFlowGraph()
        if getattr(ast, 'value', None):
            g.merge_graph(self.visit(ast.value))
        elif getattr(ast, 'exc', None):
            g.merge_graph(self.visit(ast.exc))

        op_node = OperationNode(label, ast,
                                kind=kind,
                                control=self.curr_control,
                                branch_kind=self.curr_branch_kind)
        g.add_node(op_node, LinkType.PARAMETER)
        g.statement_sinks.clear()
        return g

    def visit_Raise(self, node):
        return self._visit_dep_resetter(OperationNode.Label.RAISE, node, OperationNode.Kind.RAISE)

    def visit_Return(self, node):
        return self._visit_dep_resetter(OperationNode.Label.RETURN, node, OperationNode.Kind.RETURN)

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
        g = ExtControlFlowGraph()
        g.parallel_merge_graphs([self.visit(val) for val in node.values])

        op_node = OperationNode('fstr', node, kind=OperationNode.Kind.UNCLASSIFIED,
                                control=self.curr_control, branch_kind=self.curr_branch_kind)
        g.add_node(op_node, LinkType.PARAMETER)

        return g

    def visit_Compare(self, node):
        g = None
        last_fg = self.visit(node.left)
        for i, cmp in enumerate(node.comparators):
            op_node = OperationNode(node.ops[i].__class__.__name__, node, kind=OperationNode.Kind.COMPARE,
                                    control=self.curr_control, branch_kind=self.curr_branch_kind)
            right_fg = self.visit(cmp)

            last_fg.add_node(op_node, LinkType.PARAMETER)
            right_fg.add_node(op_node, LinkType.PARAMETER)

            fgs = [last_fg, right_fg]
            g = ExtControlFlowGraph()
            g.parallel_merge_graphs(fgs)

            last_fg = g
        return g


class GraphBuildingException(Exception):
    pass
