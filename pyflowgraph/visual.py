import graphviz as gv

from pyflowgraph.models import ExtControlFlowGraph, DataNode, OperationNode, ControlNode, ControlEdge, DataEdge, EntryNode


def _get_label_and_attrs(node, show_op_kind=True):
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

    return label, attrs


def _convert_to_visual_graph(graph: ExtControlFlowGraph, file_name: str, show_op_kind=True, show_control_branch=False,
                             separate_mapped=True):
    vg = gv.Digraph(name=file_name, format='pdf')

    used = {}
    for node in graph.nodes:
        if used.get(node):
            continue

        if separate_mapped and node.mapped:
            label, attrs = _get_label_and_attrs(node, show_op_kind=show_op_kind)
            mapped_label, mapped_attrs = _get_label_and_attrs(node.mapped, show_op_kind=show_op_kind)

            used[node] = used[node.mapped] = True

            s = gv.Digraph(f'subgraph: {node.statement_num} to {node.mapped.statement_num}')
            s.node(f'{node.statement_num}', label=label, _attributes=attrs)
            s.node(f'{node.mapped.statement_num}', label=mapped_label, _attributes=mapped_attrs)

            rank = 'source' if isinstance(node, EntryNode) else 'same'
            s.graph_attr.update(rank=rank)
            vg.subgraph(s)
        else:
            label, attrs = _get_label_and_attrs(node, show_op_kind=show_op_kind)
            vg.node(f'{node.statement_num}', label=label, _attributes=attrs)

    for node in graph.nodes:
        for edge in node.in_edges:
            label = edge.label
            attrs = {}

            if show_control_branch and isinstance(edge, ControlEdge):
                label = f'{"T" if edge.branch_kind else "F"} {label}'

            if isinstance(edge, DataEdge):
                attrs['style'] = 'dotted'

            vg.edge(str(edge.node_from.statement_num), str(edge.node_to.statement_num), xlabel=label, _attributes=attrs)

    return vg


def export_graph_image(graph: ExtControlFlowGraph, file_name: str = 'G2'):
    visual_graph = _convert_to_visual_graph(graph, file_name, show_control_branch=True)
    visual_graph.render(f'images/{file_name}')
