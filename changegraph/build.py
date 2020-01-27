import logging
import time

import pyflowgraph
from pyflowgraph.build import LinkType
from pyflowgraph.models import ExtControlFlowGraph, DataNode, OperationNode
from external.gumtree import GumTreeBuilder, GumTree
from vb_utils import LineReader


class ChangeGraphBuilder:  # TODO: should not contain hardcoded gumtree matching
    @staticmethod
    def _time_log(text, start):
        logging.warning(f'{text} {int((time.time() - start) * 1000)}ms')

    def build_from_files(self, path1, path2):
        gt_builder = GumTreeBuilder()
        gt_matches = gt_builder.get_matches(path1, path2)

        start = time.time()
        gt1, gt2 = gt_builder.build_from_file(path1), gt_builder.build_from_file(path2)
        GumTree.apply_matching(gt1, gt2, gt_matches)
        self._time_log('Gumtree... OK', start)

        start = time.time()
        fg1, fg2 = pyflowgraph.build_from_file(path1), pyflowgraph.build_from_file(path2)
        self._time_log('Flow graphs... OK', start)

        start = time.time()
        fg_to_gt1, gt_to_fg1 = self._map_gumtree_to_fg(path1, gt1, fg1)
        fg_to_gt2, gt_to_fg2 = self._map_gumtree_to_fg(path2, gt2, fg2)
        for match in gt_matches:
            src = gt1.node_id_to_node[int(match.get('src'))]
            dest = gt2.node_id_to_node[int(match.get('dest'))]

            if not gt_to_fg1.get(src):
                logging.error(f'Unable to find fg node for {src.data}')
                continue

            if not gt_to_fg2.get(dest):
                logging.error(f'Unable to find fg node for {dest.data}')
                continue

            fg_src = gt_to_fg1[src]
            fg_dest = gt_to_fg2[dest]

            fg_src.mapped = fg_dest
            fg_dest.mapped = fg_src

            fg_src.create_edge(fg_dest, LinkType.MAP)
        self._time_log('Mapping... OK', start)

        fg1.calc_changed_nodes()
        fg2.calc_changed_nodes()

        merged_fg = ExtControlFlowGraph()
        merged_fg.nodes = fg1.nodes.union(fg2.nodes)
        merged_fg.changed_nodes = fg1.changed_nodes.union(fg2.changed_nodes)

        return merged_fg

    def _map_gumtree_to_fg(self, src_path, gt, fg):  # TODO: can be optimized
        fg_node_to_gt_node = {}
        gt_node_to_fg_node = {}  # TODO CompareGt produces more than 1 node, when only the last one matched

        with open(src_path, 'r+') as f:
            lr = LineReader(''.join(f.readlines()))

        for node in fg.nodes:
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
                if node.kind == DataNode.Kind.VARIABLE:
                    type_label = GumTree.TypeLabel.NAME_LOAD
            elif isinstance(node, OperationNode):
                if node.kind == OperationNode.Kind.ASSIGN:
                    type_label = GumTree.TypeLabel.ASSIGN

            found = gt.find_node(pos, length, type_label=type_label)
            if found:
                fg_node_to_gt_node[node] = found
                gt_node_to_fg_node[found] = node
            else:
                logging.warning(f'Node {node} {node.label} {node.ast} is not mapped to any gumtree node')
                raise GraphBuildingException

        return fg_node_to_gt_node, gt_node_to_fg_node


class GraphBuildingException(Exception):
    pass
