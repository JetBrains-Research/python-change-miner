from pyflowgraph.models import DataNode, Node, OperationNode, ControlNode, LinkType


class ChangeGraph:
    def __init__(self, repo_info=None):
        self.nodes = set()
        self.repo_info = repo_info


class ChangeNode:  # todo: base class for pfg and cg
    _NODE_ID = 0

    class Property:
        SYNTAX_TOKEN_INTERVALS = Node.Property.SYNTAX_TOKEN_INTERVALS

        ALL = [SYNTAX_TOKEN_INTERVALS]

    def set_property(self, prop, value):
        self._data[prop] = value

    def get_property(self, prop, default=None):
        return self._data.get(prop, default)

    class CommonLabel:
        VARIABLE = 'var'
        LITERAL = 'lit'

    class Kind:
        DATA_NODE = 'data'
        OPERATION_NODE = 'operation'
        CONTROL_NODE = 'control'
        UNKNOWN = 'unknown'

    class Version(Node.Version):
        pass

    class SubKind:
        DATA_VARIABLE_DECL = DataNode.Kind.VARIABLE_DECL
        DATA_VARIABLE_USAGE = DataNode.Kind.VARIABLE_USAGE
        DATA_LITERAL = DataNode.Kind.LITERAL

        OP_COLLECTION = OperationNode.Kind.COLLECTION
        OP_FUNC_CALL = OperationNode.Kind.FUNC_CALL
        OP_ASSIGNMENT = OperationNode.Kind.ASSIGN
        OP_COMPARE = OperationNode.Kind.COMPARE
        OP_RETURN = OperationNode.Kind.RETURN

    def __init__(self, statement_num, ast, label, kind, version, sub_kind=None):
        ChangeNode._NODE_ID += 1
        self.id = ChangeNode._NODE_ID

        self.statement_num = statement_num
        self.ast = ast

        self.label = label
        self.in_edges = set()
        self.out_edges = set()
        self.mapped = None
        self.graph = None

        self.kind = kind
        self.sub_kind = sub_kind

        self.version = version

        self._data = {}

    @classmethod
    def create_from_fg_node(cls, fg_node):
        label = fg_node.label
        if isinstance(fg_node, DataNode):
            kind = cls.Kind.DATA_NODE
            sub_kind = fg_node.kind

            if sub_kind in [cls.SubKind.DATA_VARIABLE_DECL, cls.SubKind.DATA_VARIABLE_USAGE]:
                # label = cls.CommonLabel.VARIABLE
                label = fg_node.label
            elif sub_kind in [cls.SubKind.DATA_LITERAL]:
                label = cls.CommonLabel.LITERAL

        elif isinstance(fg_node, OperationNode):
            kind = cls.Kind.OPERATION_NODE
        elif isinstance(fg_node, ControlNode):
            kind = cls.Kind.CONTROL_NODE
        else:
            kind = cls.Kind.UNKNOWN

        created = ChangeNode(fg_node.statement_num, fg_node.ast, label, kind, fg_node.version,
                             sub_kind=getattr(fg_node, 'kind', None))

        for prop in cls.Property.ALL:
            fg_node_prop = fg_node.get_property(prop)
            if fg_node_prop is None:
                continue
            created.set_property(prop, fg_node_prop)

        return created

    def get_in_nodes(self, label=None):
        return {e.node_from for e in self.in_edges if not label or e.label == label}

    def get_out_nodes(self, label=None):
        return {e.node_to for e in self.out_edges if not label or e.label == label}

    def get_out_node_groups(self, grouping_label):
        group1 = set()
        group2 = set()
        for e in self.out_edges:
            if e.label == grouping_label:
                group1.add(e.node_to)
            else:
                group2.add(e.node_to)
        return group1, group2

    def get_definitions(self):
        defs = []
        for e in self.in_edges:
            if isinstance(e, ChangeEdge) and e.label == LinkType.REFERENCE:
                defs.append(e.node_from)
        return defs

    def set_graph(self, graph):
        self.graph = graph

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return self.id

    def __repr__(self):
        return f'#{self.id} v{self.version} {self.label} {self.kind}.{self.sub_kind}'


class ChangeEdge:
    def __init__(self, label, node_from, node_to):
        self.node_from = node_from
        self.node_to = node_to
        self.label = label

    @classmethod
    def create(cls, label, node_from, node_to):
        created = ChangeEdge(label, node_from, node_to)

        node_from.out_edges.add(created)
        node_to.in_edges.add(created)

    def __repr__(self):
        return f'#{self.node_from.id} -{self.label}> #{self.node_to.id}'
