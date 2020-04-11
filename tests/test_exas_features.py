from changegraph.models import ChangeGraph, ChangeNode, ChangeEdge
from patterns.models import Fragment
from patterns.exas import normalize
from pyflowgraph.models import LinkType


def test_vector_hash():
    cg = ChangeGraph()
    cn1 = ChangeNode(None, None, 'M1', ChangeNode.Kind.OPERATION_NODE, 0, sub_kind=ChangeNode.SubKind.OP_FUNC_CALL)
    cn2 = ChangeNode(None, None, '=', ChangeNode.Kind.OPERATION_NODE, 0, sub_kind=ChangeNode.SubKind.OP_ASSIGNMENT)
    cn3 = ChangeNode(None, None, 'M2', ChangeNode.Kind.OPERATION_NODE, 1, sub_kind=ChangeNode.SubKind.OP_FUNC_CALL)
    cn4 = ChangeNode(None, None, '=', ChangeNode.Kind.OPERATION_NODE, 1, sub_kind=ChangeNode.SubKind.OP_ASSIGNMENT)

    ChangeEdge.create(LinkType.MAP, cn1, cn3)
    ChangeEdge.create(LinkType.MAP, cn2, cn4)
    ChangeEdge.create(LinkType.PARAMETER, cn1, cn2)
    ChangeEdge.create(LinkType.PARAMETER, cn3, cn4)

    cg.nodes.update([cn1, cn2, cn3, cn4])

    fr = Fragment.create_from_node_pair([cn1, cn3])
    ext_fr = Fragment.create_extended(fr, ext_nodes=(cn2, cn4))

    vector_hash = ext_fr.vector.get_hash()
    assert vector_hash == normalize(27320942899360)


if __name__ == '__main__':
    test_vector_hash()
