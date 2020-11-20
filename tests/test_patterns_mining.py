from changegraph.models import ChangeGraph, ChangeNode, ChangeEdge
from patterns.models import Fragment, Pattern
from pyflowgraph.models import LinkType

from log import logger


def test_fragment_label_to_ext_list():
    cg = ChangeGraph()
    cn1 = ChangeNode(None, None, 'getZoneByName', ChangeNode.Kind.OPERATION_NODE, 0,
                     sub_kind=ChangeNode.SubKind.OP_FUNC_CALL)
    cn2 = ChangeNode(None, None, '=', ChangeNode.Kind.OPERATION_NODE, 0, sub_kind=ChangeNode.SubKind.OP_ASSIGNMENT)
    cn3 = ChangeNode(None, None, 'var', ChangeNode.Kind.DATA_NODE, 0, sub_kind=ChangeNode.SubKind.DATA_VARIABLE_DECL)
    cn4 = ChangeNode(None, None, 'getSettings', ChangeNode.Kind.OPERATION_NODE, 0,
                     sub_kind=ChangeNode.SubKind.OP_FUNC_CALL)
    cn5 = ChangeNode(None, None, '=', ChangeNode.Kind.OPERATION_NODE, 0, sub_kind=ChangeNode.SubKind.OP_ASSIGNMENT)
    cn6 = ChangeNode(None, None, 'var', ChangeNode.Kind.DATA_NODE, 0, sub_kind=ChangeNode.SubKind.DATA_VARIABLE_DECL)
    cn7 = ChangeNode(None, None, 'update', ChangeNode.Kind.OPERATION_NODE, 0, sub_kind=ChangeNode.SubKind.OP_FUNC_CALL)

    ChangeEdge.create(LinkType.PARAMETER, cn1, cn2)  # getZoneByName -para> =
    ChangeEdge.create(LinkType.DEFINITION, cn2, cn3)  # = -def> var
    ChangeEdge.create(LinkType.DEFINITION, cn1, cn3)  # getZoneByName -def> var
    ChangeEdge.create(LinkType.PARAMETER, cn4, cn5)  # getSettings -para> =
    ChangeEdge.create(LinkType.DEFINITION, cn4, cn6)  # getSettings -para> var
    ChangeEdge.create(LinkType.DEFINITION, cn5, cn6)  # = -para> var
    ChangeEdge.create(LinkType.PARAMETER, cn4, cn7)  # = -para> update
    ChangeEdge.create(LinkType.PARAMETER, cn5, cn7)  # = -para> update
    ChangeEdge.create(LinkType.PARAMETER, cn6, cn7)  # = -para> update

    c2n1 = ChangeNode(None, None, 'get_fw_zone_settings', ChangeNode.Kind.OPERATION_NODE, 1,
                      sub_kind=ChangeNode.SubKind.OP_FUNC_CALL)
    c2n2 = ChangeNode(None, None, '=', ChangeNode.Kind.OPERATION_NODE, 1, sub_kind=ChangeNode.SubKind.OP_ASSIGNMENT)
    c2n3 = ChangeNode(None, None, 'var', ChangeNode.Kind.DATA_NODE, 1, sub_kind=ChangeNode.SubKind.DATA_VARIABLE_DECL)
    c2n4 = ChangeNode(None, None, 'var', ChangeNode.Kind.DATA_NODE, 1, sub_kind=ChangeNode.SubKind.DATA_VARIABLE_USAGE)
    c2n5 = ChangeNode(None, None, 'var', ChangeNode.Kind.DATA_NODE, 1, sub_kind=ChangeNode.SubKind.DATA_VARIABLE_DECL)
    c2n6 = ChangeNode(None, None, 'update_fw_settings', ChangeNode.Kind.OPERATION_NODE, 1,
                      sub_kind=ChangeNode.SubKind.OP_FUNC_CALL)

    ChangeEdge.create(LinkType.PARAMETER, c2n1, c2n2)  # get_fw_zone_settings -para> =
    ChangeEdge.create(LinkType.PARAMETER, c2n2, c2n6)  # = -para> update_fw_settings
    ChangeEdge.create(LinkType.DEFINITION, c2n2, c2n3)  # = -def> var
    ChangeEdge.create(LinkType.DEFINITION, c2n2, c2n5)  # = -def> var
    ChangeEdge.create(LinkType.REFERENCE, c2n3, c2n4)  # var -ref> var
    ChangeEdge.create(LinkType.PARAMETER, c2n3, c2n6)  # var -para> update_fw_settings
    ChangeEdge.create(LinkType.PARAMETER, c2n4, c2n6)  # var -para> update_fw_settings
    ChangeEdge.create(LinkType.PARAMETER, c2n5, c2n6)  # var -para> update_fw_settings

    # ---

    ChangeEdge.create(LinkType.MAP, cn1, c2n1)  # getZoneByName -> get_fw_zone_settings
    ChangeEdge.create(LinkType.MAP, cn2, c2n2)  # = -> =
    ChangeEdge.create(LinkType.MAP, cn7, c2n6)  # update -> update_fw_settings
    cn1.mapped = c2n1
    c2n1.mapped = cn1
    cn2.mapped = c2n2
    c2n2.mapped = cn2
    cn7.mapped = c2n6
    c2n6.mapped = cn7

    cg.nodes.update([cn1, cn2, cn3, cn4, cn5, cn6, cn7])
    cg.nodes.update([c2n1, c2n2, c2n3, c2n4, c2n5, c2n6])

    # 4 v1 get_fw_zone_settings operation.method-call
    # 5 v0 getZoneByName operation.method-call
    # 6 v0 getSettings operation.method-call
    # 7 v1 var data.variable-decl
    # 8 v1 = operation.assignment
    # 9 v0 = operation.assignment
    # 10 v0 = operation.assignment
    # 11 v1 var data.variable-decl
    # 1 v0 update operation.method-call
    # 12 v0 var data.variable-decl
    # 2 v1 update_fw_settings operation.method-call
    # 13 v1 var data.variable-usage
    # 3 v0 var data.variable-decl

    # for node in cg.nodes:
    #     logger.log(logger.WARNING, node)
    #
    # export_graph_image(cg)

    # --- --- --- --- ---

    fr = Fragment.create_from_node_pair([cn1, c2n1])
    group = _get_freq_group(fr)

    p = Pattern(group, freq=None)
    assert p.size > 0


def _get_freq_group(fr):
    max_freq = 0
    freq_group = None

    label_to_ext_list = fr.get_label_to_ext_list()
    for label, ext_list in label_to_ext_list.items():
        ext_fragments = set()
        for ext in ext_list:
            ext_fr = Fragment.create_extended(fr, ext)
            ext_fragments.add(ext_fr)

            groups = Fragment.create_groups(ext_fragments)
            for num, group in enumerate(groups):
                freq = len(group)
                if freq > max_freq:
                    max_freq = freq
                    freq_group = group

                logger.log(logger.DEBUG, f'Elements in group #{num + 1} -> {len(group)}')

    return freq_group


def init():
    Pattern.MIN_FREQUENCY = 1
    #

    if __name__ == '__main__':
        test_fragment_label_to_ext_list()


init()
