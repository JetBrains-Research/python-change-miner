import graphviz as gv

from pyflowgraph.models import ExtControlFlowGraph, DataNode, OperationNode, ControlNode, ControlEdge, DataEdge


def _convert_to_visual_graph(graph: ExtControlFlowGraph, file_name: str, show_op_kind=True, show_control_branch=False):
    vg = gv.Digraph(name=file_name, format='pdf')

    node_to_node_number = {}
    for id, node in enumerate(graph.nodes):
        label = f'{node.label}'

        attrs = {}
        if isinstance(node, DataNode):
            attrs['shape'] = 'ellipse'
            if show_op_kind:
                label = f'{label} <{node.kind}>'
        elif isinstance(node, OperationNode):
            attrs['shape'] = 'box'
            if show_op_kind:
                label = f'{label} <{node.kind}>'
        elif isinstance(node, ControlNode):
            attrs['shape'] = 'diamond'

        vg.node(f'{id}', label=label, _attributes=attrs)
        node_to_node_number[node] = id

    for id, node in enumerate(graph.nodes):
        for edge in node.in_edges:
            label = edge.label
            attrs = {}

            if show_control_branch and isinstance(edge, ControlEdge):
                label = f'{"T" if edge.branch_kind else "F"} {label}'

            if isinstance(edge, DataEdge):
                attrs['style'] = 'dotted'

            vg.edge(str(node_to_node_number[edge.node_from]),
                    str(node_to_node_number[edge.node_to]),
                    label=label,
                    _attributes=attrs)

    return vg


def export_graph_image(graph: ExtControlFlowGraph, file_name: str = 'G2'):
    visual_graph = _convert_to_visual_graph(graph, file_name, show_control_branch=True)
    visual_graph.render(f'images/{file_name}')