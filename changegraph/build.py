import logging
import time
import os

import pyflowgraph
from changegraph.models import ChangeNode, ChangeGraph, ChangeEdge
from pyflowgraph.models import ExtControlFlowGraph, Node
from external.gumtree import GumTree
from external import gumtree
import vb_utils


class ChangeGraphBuilder:  # TODO: should not contain hardcoded gumtree matching
    def build_from_files(self, path1, path2, repo_info=None):
        process_id = os.getpid()

        logging.warning(f'#{process_id}: Change graph building...')
        gt_matches = gumtree.get_matches(path1, path2)

        start = time.time()
        gt1, gt2 = gumtree.build_from_file(path1), gumtree.build_from_file(path2)
        GumTree.apply_matching(gt1, gt2, gt_matches)
        vb_utils.time_log(f'#{process_id}: Gumtree... OK', start)

        start = time.time()
        fg1, fg2 = pyflowgraph.build_from_file(path1), pyflowgraph.build_from_file(path2)
        vb_utils.time_log(f'#{process_id}: Flow graphs... OK', start)

        start = time.time()
        fg1.map_to_gumtree(gt1)
        fg2.map_to_gumtree(gt2)
        ExtControlFlowGraph.map_by_gumtree(fg1, fg2, gt_matches)
        vb_utils.time_log(f'#{process_id}: Mapping... OK', start)

        start = time.time()
        for node in fg2.nodes:
            node.version = Node.Version.AFTER_CHANGES
        cg = self._create_change_graph(fg1, fg2, repo_info=repo_info)
        vb_utils.time_log(f'#{process_id}: Change graph... OK', start)

        return cg

    @staticmethod
    def _create_change_graph(fg1, fg2, repo_info=None):
        fg1.calc_changed_nodes_by_gumtree()
        fg2.calc_changed_nodes_by_gumtree()

        fg_changed_nodes = fg1.changed_nodes.union(fg2.changed_nodes)
        fg_node_to_cg_node = {}

        cg = ChangeGraph(repo_info=repo_info)
        for fg_node in fg_changed_nodes:
            if fg_node_to_cg_node.get(fg_node):
                continue

            node = ChangeNode.create_from_fg_node(fg_node)
            cg.nodes.add(node)
            node.set_graph(cg)  # todo: probably better to create method 'add_node'
            fg_node_to_cg_node[fg_node] = node

            if fg_node.mapped and fg_node.mapped in fg_changed_nodes:
                mapped_node = ChangeNode.create_from_fg_node(fg_node.mapped)
                cg.nodes.add(mapped_node)
                mapped_node.set_graph(cg)
                fg_node_to_cg_node[fg_node.mapped] = mapped_node

                node.mapped = mapped_node
                mapped_node.mapped = node

        for fg_node in fg_changed_nodes:
            for e in fg_node.in_edges:
                if e.node_from in fg_changed_nodes:
                    ChangeEdge.create(e.label, fg_node_to_cg_node[e.node_from], fg_node_to_cg_node[e.node_to])
        return cg


class GraphBuildingException(Exception):
    pass
