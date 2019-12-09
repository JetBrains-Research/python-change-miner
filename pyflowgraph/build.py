import ast

from pyflowgraph import DataNode, OperationNode, ExtControlFlowGraph, ControlNode, DataEdge
from pyflowgraph.models import LinkType, EntryNode


class BuildingContext:
    def __init__(self):
        self.local_variables = []
        self.controls = []

    def add_scope(self):
        self.local_variables.append({})

    def remove_scope(self):
        self.local_variables.pop()

    def add_variable(self, id, ast):
        self.local_variables[-1][id] = {
            'id': id,
            'ast': ast
        }

    def get_variable_info(self, id):
        for local_variables in self.local_variables:
            var = local_variables.get(id)
            if var is not None:
                return var


class GraphBuilder:
    def __init__(self):
        self.ast_visitor = ASTVisitor()

    def build_from_source(self, source_code, make_closure=True):
        source_code_ast = ast.parse(source_code, mode='exec')
        fg = self.ast_visitor.visit(source_code_ast)
        if make_closure:
            fg = self.make_closure(fg)
        return fg

    def build_from_file(self, file_path, make_closure=True):
        with open(file_path, 'r+') as f:
            data = f.read()
            f.close()
        return self.build_from_source(data, make_closure)

    def _build_flow_graph(self, source_code):
        py_ast = ast.parse(source_code, mode='exec')
        return self.ast_visitor.visit(py_ast)

    @staticmethod
    def make_closure(fg):  # FIXME
        for node in fg.nodes:
            pass
        return fg


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

    def get_assign_graph_and_vars(self, target, prepared_value):
        if isinstance(target, ast.Name):
            val_fg = prepared_value
            var_node = DataNode(target.id, target, self.visitor.curr_control, self.visitor._gen_var_key(target),
                                kind=DataNode.Kind.VARIABLE)
            op_node = OperationNode('=', target, kind=OperationNode.Kind.ASSIGN,
                                    control=self.visitor.curr_control, branch_kind=self.visitor.curr_branch_kind)
            val_fg.add_node(op_node, LinkType.PARAMETER)
            val_fg.add_node(var_node, LinkType.DEFINITION)

            var = target.id, target
            return val_fg, [var]
        elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):  # Starred appears inside collections
            vars = []
            if isinstance(prepared_value, ExtControlFlowGraph):
                assign_group = self._get_assign_group(target)
                fgs = []

                for el in assign_group:
                    fg, curr_vars = self.get_assign_graph_and_vars(el, ExtControlFlowGraph())
                    fgs.append(fg)
                    vars += curr_vars

                prepared_value.parallel_merge_graphs(fgs, op_link_type=LinkType.DEFINITION)
                return prepared_value, vars
            else:
                g = ExtControlFlowGraph()
                for i, el in enumerate(target.elts):
                    fg, curr_vars = self.get_assign_graph_and_vars(el, prepared_value[i])
                    g.merge_graph(fg)
                    vars += curr_vars
                return g, vars
        elif isinstance(target, ast.Starred):
            return self.get_assign_graph_and_vars(target.value, prepared_value)

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
        if isinstance(target, ast.Name):
            return self.visitor.visit(value)
        elif isinstance(target, ast.Tuple) or isinstance(target, ast.List):
            prepared_arr = []
            if isinstance(value, ast.Call):
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
            raise GraphBuildingException

    def visit_assign(self, node):
        """
        possible targets are Attribute-, Subscript-, Slicing-, Starred+, Name+, List+, Tuple+
        """
        g = ExtControlFlowGraph()
        assigned_vars = []
        for target in node.targets:
            prepared_value = self.prepare_assign_values(target, node.value)
            fg, vars = self.get_assign_graph_and_vars(target, prepared_value)
            assigned_vars += vars
            g.merge_graph(fg)

        for var in assigned_vars:
            id, node = var
            self.visitor.context.add_variable(id, node)

        return g


class ASTVisitor(ast.NodeVisitor):
    def __init__(self):
        self.context = BuildingContext()
        self.fg = ExtControlFlowGraph()
        self.curr_control = None
        self.curr_branch_kind = True

        self.control_branch_stack = [(self.curr_control, self.curr_branch_kind)]
        self.visitor_helper = ASTVisitorHelper(self)

    def build_flow_graph(self, source_code):
        py_ast = ast.parse(source_code, mode='exec')
        return self.visit(py_ast)

    @staticmethod
    def _gen_var_key(var):
        return f'{var.id}'

    def _switch_control_branch(self, new_control, new_branch_kind, replace=False):
        old_control = self.curr_control
        old_branch_kind = self.curr_branch_kind
        self.curr_control = new_control
        self.curr_branch_kind = new_branch_kind
        if replace:
            del self.control_branch_stack[-1]
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

    def _visit_op(self, op_name, op_node, op_kind, params):
        op_node = OperationNode(op_name, op_node, kind=op_kind,
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

    # Root visits
    def visit_Module(self, node):
        entry_node = EntryNode('START', node, control=None)
        self.fg.set_entry_node(entry_node)
        self._switch_control_branch(entry_node, True)

        self.context.add_scope()
        for st in node.body:
            self.fg.merge_graph(self.visit(st))
        self.context.remove_scope()

        self._pop_control_branch()
        return self.fg

    def visit_Expr(self, node):
        return self.visit(node.value)

    # Visit literals, variables and collections
    def visit_Str(self, node):
        return ExtControlFlowGraph(node=DataNode(node.s, node, self.curr_control, kind=DataNode.Kind.LITERAL))

    def visit_Num(self, node):
        return ExtControlFlowGraph(node=DataNode(node.n, node, self.curr_control, kind=DataNode.Kind.LITERAL))

    def visit_NameConstant(self, node):
        return ExtControlFlowGraph(node=DataNode(node.value, node, self.curr_control, kind=DataNode.Kind.LITERAL))

    def visit_Constant(self, node):
        return ExtControlFlowGraph(node=DataNode(node.value, node, self.curr_control, kind=DataNode.Kind.LITERAL))

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
            key_value_fg = self._visit_bin_op(node, key, node.values[n], op_name=':',
                                              op_kind=OperationNode.Kind.UNCLASSIFIED)
            fg_graphs.append(key_value_fg)

        g = ExtControlFlowGraph()
        g.parallel_merge_graphs(fg_graphs)
        op_node = OperationNode('Dict', node, kind=OperationNode.Kind.COLLECTION,
                                control=self.curr_control, branch_kind=self.curr_branch_kind)
        g.add_node(op_node, LinkType.PARAMETER)
        return g

    def visit_Name(self, node):
        # FIXME: considered that we visit only variable names
        var_info = self.context.get_variable_info(node.id)
        var_key = self._gen_var_key(var_info['ast']) if var_info else self._gen_var_key(node)

        g = ExtControlFlowGraph()
        g.add_node(node=DataNode(node.id, node, self.curr_control, key=var_key, kind=DataNode.Kind.VARIABLE))
        return g

    # Visit operations
    def visit_BinOp(self, node):
        return self._visit_bin_op(node.op, node.left, node.right)

    def visit_BoolOp(self, node):
        return self._visit_op(node.op.__class__.__name__.lower(), node.op, OperationNode.Kind.UNCLASSIFIED, node.values)

    def visit_UnaryOp(self, node):
        return self._visit_op(node.op.__class__.__name__, node.op, OperationNode.Kind.UNCLASSIFIED, [node.operand])

    def visit_Assign(self, node):
        return self.visitor_helper.visit_assign(node)

    def visit_AugAssign(self, node):
        if isinstance(node.target, ast.Name):
            fg, _ = self.visitor_helper.get_assign_graph_and_vars(
                node.target, self._visit_bin_op(node.op, node.target, node.value))
            self.context.add_variable(node.target.id, node.target)
            return fg
        else:
            raise GraphBuildingException

    def visit_AnnAssign(self, node):
        if not node.value:
            return ExtControlFlowGraph()

        prepared_value = self.visitor_helper.prepare_assign_values(node.target, node.value)
        fg, vars = self.visitor_helper.get_assign_graph_and_vars(node.target, prepared_value)
        for var in vars:
            id, node = var
            self.context.add_variable(id, node)

        return fg

    def visit_Call(self, node):
        if isinstance(node.func, ast.Name):
            arg_fgs = []
            for arg in node.args:
                arg_fgs.append(self.visit(arg))

            g = ExtControlFlowGraph()
            g.parallel_merge_graphs(arg_fgs)
            op_node = OperationNode(node.func.id, node.func, kind=OperationNode.Kind.FUNCTION,
                                    control=self.curr_control, branch_kind=self.curr_branch_kind)
            g.add_node(op_node, LinkType.PARAMETER)
            return g
        elif isinstance(node.func, ast.Attribute):
            val_fg = self.visit(node.func.value)

            func_node = OperationNode(node.func.attr, node.func, kind=OperationNode.Kind.FUNCTION,
                                      control=self.curr_control, branch_kind=self.curr_branch_kind)
            val_fg.add_node(func_node, LinkType.RECEIVER)
            return val_fg

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
        control_node = ControlNode('if', node, self.curr_control)
        fg = self.visit(node.test)
        fg.add_node(control_node, LinkType.CONDITION)

        self._switch_control_branch(control_node, True)
        fg1 = ExtControlFlowGraph()
        for st in node.body:
            fg1.merge_graph(self.visit(st))

        self._switch_control_branch(control_node, False, replace=True)
        fg2 = ExtControlFlowGraph()
        for st in node.orelse:
            fg2.merge_graph(self.visit(st))

        fg.parallel_merge_graphs([fg1, fg2])
        self._pop_control_branch()
        return fg

    def visit_For(self, node):
        prepared_value = self.visitor_helper.prepare_assign_values(node.target, node.iter)
        fg, vars = self.visitor_helper.get_assign_graph_and_vars(node.target, prepared_value)
        for var in vars:
            id, var_node = var
            self.context.add_variable(id, var_node)
        # TODO: could be merged with AnnAssign

        control_node = ControlNode('for', node, self.curr_control)
        fg.add_node(control_node)

        for op_node in fg.op_nodes:
            DataEdge(LinkType.CONDITION, node_from=op_node, node_to=control_node)

        self._switch_control_branch(control_node, True)
        for st in node.body:
            fg.merge_graph(self.visit(st))
        self._pop_control_branch()
        return fg

    def visit_Pass(self, _):
        return ExtControlFlowGraph()

    # Return/continue/break
    def visit_Return(self, node):
        g = ExtControlFlowGraph()
        g.add_node(OperationNode('return', node,
                                 kind=OperationNode.Kind.RETURN,
                                 control=self.curr_control,
                                 branch_kind=self.curr_branch_kind))
        return g

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
            op_node = OperationNode(node.ops[i].__class__.__name__, node.ops[i], kind=OperationNode.Kind.COMPARE,
                                    control=self.curr_control, branch_kind=self.curr_branch_kind)
            right_fg = self.visit(cmp)

            last_fg.add_node(op_node, LinkType.PARAMETER)
            right_fg.add_node(op_node, LinkType.PARAMETER)

            fgs = [last_fg, right_fg]
            g = ExtControlFlowGraph()
            g.parallel_merge_graphs(fgs)

            last_fg = g
        return g


class EntryNodeDuplicated(Exception):
    pass


class GraphBuildingException(Exception):
    pass
