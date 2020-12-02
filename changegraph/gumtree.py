import json
import subprocess
from enum import Enum

import settings


def parse(src_path):
    gumtree_bin_path = settings.get('gumtree_bin_path')
    args = [gumtree_bin_path, 'parse', src_path]
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    result, _ = p.communicate()
    return json.loads(result) if result else {}


def diff(src1_path, src2_path):
    gumtree_bin_path = settings.get('gumtree_bin_path')
    args = [gumtree_bin_path, 'jsondiff', src1_path, src2_path]
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    result, _ = p.communicate()
    return json.loads(result) if result else {}


def get_matches_and_actions(src1_path, src2_path):
    result = diff(src1_path, src2_path)
    return result.get('matches', {}), result.get('actions', {})


def build_from_file(src_path):
    parsed = parse(src_path)
    return GumTree(src_path, parsed)


class GumTree:
    class ActionType:
        UPDATE = 'update'
        DELETE = 'delete'
        INSERT = 'insert'
        MOVE = 'move'

    class TypeLabel:
        NAME_STORE = 'Name_Store'
        NAME_LOAD = 'Name_Load'
        FUNC_CALL = 'Call'
        FUNC_DEF = 'FunctionDef'
        ASSIGN = 'Assign'
        EXPR = 'Expr'
        SUBSCRIPT_STORE = 'Subscript_Store'
        SUBSCRIPT_LOAD = 'Subscript_Load'
        ATTRIBUTE_STORE = 'Attribute_Store'
        ATTRIBUTE_LOAD = 'Attribute_Load'
        ATTR = 'attr'
        RETURN = 'Return'
        ARGS = 'arguments'
        SIMPLE_ARGS = 'args'
        DEFAULT_ARGS = 'defaults'
        SIMPLE_ARG = 'arg'
        KEYWORD = 'keyword'
        LISTCOMP = 'ListComp'
        DICTCOMP = 'DictComp'

    def __init__(self, source_path, data):
        self.node_id_to_node = {}
        self.nodes = []

        self._data = data
        self.cnt = self._read_data(self._data.get('root', {}), start_value=0)

        self.root = self.nodes[-1]
        self.source_path = source_path
        self.matches = {}
        self.actions = {}

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

        for child_node in node.children:
            child_node.parent = node

        self.nodes.append(node)
        self.node_id_to_node[node.id] = node

        return node, val + 1

    def find_node(self, pos, length, start_node=None, type_label=None):
        node = start_node

        if node is None:
            node = self.root

        if node.pos == pos and node.length == length:
            if type_label is None or node.type_label == type_label:
                return node

        if node.children:
            for child in node.children:
                result = self.find_node(pos, length, start_node=child, type_label=type_label)
                if result:
                    return result

        return False

    @staticmethod
    def map(gt_src, gt_dest):
        matches, actions = get_matches_and_actions(gt_src.source_path, gt_dest.source_path)

        GumTree._apply_matching(gt_src, gt_dest, matches)
        GumTree._apply_actions(gt_src, gt_dest, actions)
        GumTree._adjust_changes(gt_src, gt_dest)

    @staticmethod
    def _apply_matching(gt_src, gt_dest, matches):
        gt_src.matches = gt_dest.matches = matches

        for match in matches:
            src = gt_src.node_id_to_node[int(match.get('src'))]
            dest = gt_dest.node_id_to_node[int(match.get('dest'))]

            src.mapped = dest
            dest.mapped = src

    @staticmethod
    def _apply_actions(gt_src, gt_dest, actions):
        gt_src.actions = gt_dest.actions = actions

        for action in actions:
            action_name = action['action']
            node_id = int(action['tree'])

            if action_name == GumTree.ActionType.UPDATE:
                node1 = gt_src.node_id_to_node[node_id]
                node1.status = GumTreeNode.STATUS.UPDATED
                node1.mapped.status = GumTreeNode.STATUS.UPDATED
            elif action_name == GumTree.ActionType.DELETE:
                node1 = gt_src.node_id_to_node[node_id]
                node1.status = GumTreeNode.STATUS.DELETED
            elif action_name == GumTree.ActionType.MOVE:
                node1 = gt_src.node_id_to_node[node_id]
                node1.status = GumTreeNode.STATUS.MOVED
                node1.mapped.status = GumTreeNode.STATUS.MOVED
            elif action_name == GumTree.ActionType.INSERT:
                node2 = gt_dest.node_id_to_node[node_id]
                node2.status = GumTreeNode.STATUS.INSERTED
            else:
                raise ValueError('Undefined action given by gumtree diff')

    @classmethod
    def _adjust_changes(cls, gt_src, gt_dest):
        gt_src.dfs(fn_before=cls._before_change_detector, fn_after=cls._change_detector)
        gt_dest.dfs(fn_before=cls._before_change_detector, fn_after=cls._change_detector)

    @classmethod
    def _before_change_detector(cls, node):
        # parent = node.parent
        # if parent:
        #     if parent.type_label in [GumTree.TypeLabel.KEYWORD] and parent.status == GumTreeNode.STATUS.MOVED:
        #         node.status = GumTreeNode.STATUS.MOVED
        return True

    @classmethod
    def _change_detector(cls, node):
        if node.status in [GumTreeNode.STATUS.INSERTED, GumTreeNode.STATUS.DELETED]:
            return True

        is_changed = not node.mapped or not node.is_equal(node.mapped)
        if not is_changed:
            if not node.children:
                is_changed = bool(len(node.mapped.children))
            else:
                is_changed = not len(node.mapped.children)
                if not is_changed:
                    ignore_child_ids = []
                    if node.type_label in [GumTree.TypeLabel.FUNC_CALL, GumTree.TypeLabel.ATTRIBUTE_LOAD]:
                        name_node = node.children[0]
                        is_changed = bool(name_node.status != GumTreeNode.STATUS.UNCHANGED)
                        ignore_child_ids.append(name_node.id)

                    if not is_changed:
                        is_changed = cls._are_children_changed(node, ignore_child_ids=ignore_child_ids)

        if not is_changed:
            node.status = GumTreeNode.STATUS.UNCHANGED
            if node.mapped:
                node.mapped.status = GumTreeNode.STATUS.UNCHANGED

        return is_changed

    @staticmethod
    def _are_children_changed(node, /, *, ignore_child_ids=None):
        children = [child for child in node.children if child.id not in ignore_child_ids]
        if not children:
            return False

        for child in children:
            if child.status == GumTreeNode.STATUS.UNCHANGED:
                return False
        return True

    @classmethod
    def _do_dfs(cls, node, visited, fn_before=None, fn_after=None):
        if fn_before:
            if not fn_before(node):
                return

        for child in node.children:
            if not visited.get(child.id):
                cls._do_dfs(child, visited, fn_before=fn_before, fn_after=fn_after)

        visited[node.id] = True

        if fn_after:
            fn_after(node)

    def dfs(self, fn_before=None, fn_after=None, start_node=None):
        self._do_dfs(start_node or self.root, {}, fn_before=fn_before, fn_after=fn_after)


class GumTreeNode:
    class STATUS(Enum):
        UNCHANGED = 0
        CHANGED = 1
        INSERTED = 2
        DELETED = 3
        MOVED = 4
        UPDATED = 5

        def __lt__(self, other):
            if self.__class__ is other.__class__:
                return self.value < other.value
            raise TypeError

    def __init__(self, data):
        self.id = data['id']

        self.pos = int(data['pos'])
        self.length = int(data['length'])
        self.type_label = data['typeLabel']
        self.label = data.get('label')  # e.g. present in AttributeLoad.attr
        self.children = []

        self.data = data
        self.mapped = None

        self.fg_node = None

        self.parent = None
        self.status = GumTreeNode.STATUS.CHANGED

    def is_changed(self):
        if self.status != GumTreeNode.STATUS.UNCHANGED:
            return True

        if self.parent and self.parent.type_label == GumTree.TypeLabel.EXPR:
            if self.parent.status != GumTreeNode.STATUS.UNCHANGED:
                return True

        return False

    def is_equal(self, node):
        fst_data = {k: self.data[k] for k in self.data.keys() if k in ['label', 'type', 'typeLabel']}
        snd_data = {k: node.data[k] for k in node.data.keys() if k in ['label', 'type', 'typeLabel']}
        return fst_data == snd_data

    def get_child_by_type_label(self, type_label):
        for child in self.children:
            if child.type_label == type_label:
                return child
        return None

    def __repr__(self):
        return f'#{self.id} {self.type_label} {self.label} [{self.pos}:{self.length}]'


class MappingException(Exception):
    pass
