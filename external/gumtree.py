import json
import subprocess

import settings


class GumTreeBuilder:
    def _parse(self, src_path):
        gumtree_bin_path = settings.get('gumtree_bin_path')
        result = subprocess.run([gumtree_bin_path, 'parse', src_path], stdout=subprocess.PIPE).stdout.decode('utf-8')
        return json.loads(result)

    def _diff(self, src1_path, src2_path):
        gumtree_bin_path = settings.get('gumtree_bin_path')
        args = [gumtree_bin_path, 'jsondiff', src1_path, src2_path]
        result = subprocess.run(args, stdout=subprocess.PIPE).stdout.decode('utf-8')
        return json.loads(result)

    def get_matches(self, src1_path, src2_path):
        return self._diff(src1_path, src2_path).get('matches', {})

    def build_from_file(self, src_path):
        parsed = self._parse(src_path)
        return GumTree(parsed)


class GumTree:
    class TypeLabel:
        NAME_LOAD = 'NameLoad'
        CALL = 'Call'
        ASSIGN = 'Assign'
        EXPR = 'Expr'

    def __init__(self, data):
        self.node_id_to_node = {}
        self.nodes = []

        self._data = data
        self.cnt = self._read_data(self._data.get('root', {}), start_value=0)

        self.root = self.nodes[-1]

    def _read_data(self, start_node, start_value=0):
        val = start_value

        child_nodes = []
        children = start_node.get('children')

        if children:
            for child in children:
                child_node, val = self._read_data(child, start_value=val)
                child_nodes.append(child_node)

        node = GumTreeNode(id=val, data=start_node)
        node.children = child_nodes

        self.nodes.append(node)
        self.node_id_to_node[node.id] = node

        return node, val+1

    def find_node(self, pos, length, start_node=None, type_label=None):
        if start_node is None:
            start_node = self.root

        if start_node.pos == pos and start_node.length == length:
            if type_label is None or start_node.type_label == type_label:
                return start_node

        if start_node.children:
            for child in start_node.children:
                result = self.find_node(pos, length, start_node=child)
                if result:
                    return result

        return False

    @staticmethod
    def apply_matching(gt_src, gt_dest, matches):
        for match in matches:
            src = gt_src.node_id_to_node[int(match.get('src'))]
            dest = gt_dest.node_id_to_node[int(match.get('dest'))]

            src.mapped = dest
            dest.mapped = src


class GumTreeNode:
    def __init__(self, id, data):
        self.id = id

        self.pos = int(data['pos'])
        self.length = int(data['length'])
        self.type_label = data['typeLabel']
        self.children = []

        self.data = data
        self.mapped = None
