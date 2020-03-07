import json
import subprocess

import settings


def parse(src_path):
    gumtree_bin_path = settings.get('gumtree_bin_path')
    result = subprocess.run([gumtree_bin_path, 'parse', src_path], stdout=subprocess.PIPE).stdout.decode('utf-8')
    return json.loads(result)


def diff(src1_path, src2_path):
    gumtree_bin_path = settings.get('gumtree_bin_path')
    args = [gumtree_bin_path, 'jsondiff', src1_path, src2_path]
    result = subprocess.run(args, stdout=subprocess.PIPE).stdout.decode('utf-8')
    return json.loads(result) if result else {}


def get_matches(src1_path, src2_path):
    return diff(src1_path, src2_path).get('matches', {})


def build_from_file(src_path):
    parsed = parse(src_path)
    return GumTree(src_path, parsed)


class GumTree:
    class TypeLabel:
        NAME_STORE = 'NameStore'
        NAME_LOAD = 'NameLoad'
        CALL = 'Call'
        ASSIGN = 'Assign'
        EXPR = 'Expr'

    def __init__(self, source_path, data):
        self.node_id_to_node = {}
        self.nodes = []

        self._data = data
        self.cnt = self._read_data(self._data.get('root', {}), start_value=0)

        self.root = self.nodes[-1]
        self.source_path = source_path

    def _read_data(self, start_node, start_value=0):
        val = start_value

        child_nodes = []
        children = start_node.get('children')

        if children:
            for child in children:
                child_node, val = self._read_data(child, start_value=val)
                child_nodes.append(child_node)

        start_node['id'] = val
        node = GumTreeNode(data=start_node)
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
                result = self.find_node(pos, length, start_node=child, type_label=type_label)
                if result:
                    return result

        return False

    @classmethod
    def apply_matching(cls, gt_src, gt_dest, matches):  # TODO: second call is not allowed yet
        for match in matches:
            src = gt_src.node_id_to_node[int(match.get('src'))]
            dest = gt_dest.node_id_to_node[int(match.get('dest'))]

            src.mapped = dest
            dest.mapped = src

        # TODO: is_changed flags not set to False
        def change_detector(node):  # TODO: can be optimised
            node.is_changed = not node.mapped or not node.is_equal(node.mapped)
            if node.is_changed:
                return

            if not node.children:
                node.is_changed = bool(len(node.mapped.children))
            else:
                node.is_changed = not len(node.mapped.children)
                if not node.is_changed:
                    for child in node.children:
                        if not child.is_changed:
                            break
                    else:
                        node.is_changed = True
        gt_src.dfs(fn_after=change_detector)
        gt_dest.dfs(fn_after=change_detector)

    @classmethod
    def _do_dfs(cls, node, visited, fn_before=None, fn_after=None):
        if fn_before:
            fn_before(node)

        for child in node.children:
            if not visited.get(child.id):
                cls._do_dfs(child, visited, fn_before=fn_before, fn_after=fn_after)

        visited[node.id] = True

        if fn_after:
            fn_after(node)

    def dfs(self, fn_before=None, fn_after=None):
        self._do_dfs(self.root, {}, fn_before=fn_before, fn_after=fn_after)


class GumTreeNode:
    def __init__(self, data):
        self.id = data['id']

        self.pos = int(data['pos'])
        self.length = int(data['length'])
        self.type_label = data['typeLabel']
        self.children = []

        self.data = data
        self.mapped = None

        self.fg_node = None
        self.is_changed = None

    def is_equal(self, node):
        fst_data = {k: self.data[k] for k in self.data.keys() if k in ['type', 'typeLabel']}
        snd_data = {k: node.data[k] for k in node.data.keys() if k in ['type', 'typeLabel']}
        return fst_data == snd_data
