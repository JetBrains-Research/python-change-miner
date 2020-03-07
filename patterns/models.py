import copy

from pyflowgraph.models import LinkType, Node
from changegraph.models import ChangeNode
from patterns.exas import ExasFeature
import settings
import vb_utils


class CharacteristicVector:
    """
    Characteristic vector is built by exas features' occurrences
    """
    def __init__(self):
        self.data = {}

    def add_feature(self, feature_id):
        self.data[feature_id] = self.data.get(feature_id, 0) + 1

    def get_hash(self):
        result = 0
        for key in sorted(self.data.keys()):
            result = result * 31 + self.data[key]
        return result


class Fragment:
    """
    Potential cloned parts in a software artifact are called fragments
    A fragment is a weakly connected sub-graph in the corresponding representation graph

    Read more: "Accurate and Efficient Structural Characteristic Feature Extraction"
    """
    LABEL_SEPARATOR = '-'

    def __init__(self):
        self.parent = None
        self.graph = None
        self.nodes = set()
        self.vector = CharacteristicVector()

    @classmethod
    def create_from_node_pair(cls, pair):
        f = Fragment()
        f.nodes.add(pair[0])
        f.nodes.add(pair[1])
        f.graph = pair[0].graph

        f.__init_vector_from_pair(pair)

        return f

    def __init_vector_from_pair(self, pair):
        exas_feature = ExasFeature(nodes=[pair[0], pair[1]])

        self.vector.add_feature(exas_feature.get_id_by_label(pair[0].label))
        self.vector.add_feature(exas_feature.get_id_by_label(pair[1].label))

        self.vector.add_feature(exas_feature.get_id_by_labels(labels=[pair[0].label, LinkType.MAP, pair[1].label]))

    @classmethod
    def create_extended(cls, fragment, ext_nodes):
        f = Fragment()
        f.parent = fragment
        f.graph = fragment.graph

        f.nodes = copy.copy(fragment.nodes)
        f.vector = copy.copy(fragment.vector)

        for node in ext_nodes:
            f.nodes.add(node)
            f.__recalc_vector(node, f.nodes)

        return f

    def __recalc_vector(self, node, ext_nodes):
        exas_feature = ExasFeature(nodes=ext_nodes)
        sequence = [node.label]
        self.__exas_backward_dfs(node, node, sequence, exas_feature)

    def __exas_backward_dfs(self, first_node, last_node, sequence, exas_feature):
        self.__exas_forward_dfs(last_node, sequence, exas_feature)

        if len(sequence) < ExasFeature.MAX_LENGTH:
            for e in first_node.in_edges:
                if e.node_from in self.nodes:
                    sequence.insert(0, e.label)
                    sequence.insert(0, e.node_from.label)
                    self.__exas_backward_dfs(e.node_from, last_node, sequence, exas_feature)
                    del sequence[0]
                    del sequence[0]

    def __exas_forward_dfs(self, node, sequence, exas_feature):
        feature_id = exas_feature.get_id_by_labels(sequence)
        self.vector.add_feature(feature_id)

        if len(sequence) < ExasFeature.MAX_LENGTH:
            for e in node.out_edges:
                if e.node_to in self.nodes:
                    sequence.append(e.label)
                    sequence.append(e.node_to.label)
                    self.__exas_forward_dfs(node, sequence, exas_feature)
                    del sequence[-1]
                    del sequence[-1]

    def get_label_to_extensions(self):
        """
        An extension is a list of nodes, with which we can extend a graph of the fragment
        """
        adjacent_nodes = set()
        for node in self.nodes:
            for in_node in node.get_in_nodes():
                if in_node not in self.nodes:
                    adjacent_nodes.add(in_node)

            for out_node in node.get_out_nodes():
                if out_node not in self.nodes:
                    adjacent_nodes.add(out_node)

        label_to_extensions = {}
        for node in adjacent_nodes:
            # FIXME: what the hell below?
            # if ((node.isCoreAction() | | node.isControl())
            # & & lasts[node.getVersion()] != null
            # & & node.getLabel().equals(lasts[node.getVersion()].getLabel()))
            # continue;
            if node.kind == ChangeNode.Kind.DATA_NODE:
                if node.sub_kind == ChangeNode.SubKind.DATA_LITERAL:
                    self._add_extensions(label_to_extensions, node)
                else:
                    defs = node.get_definitions()
                    if not defs:
                        refs, non_refs = node.get_out_nodes(separation_label=LinkType.REFERENCE)
                        if non_refs.intersection(self.nodes):
                            self._add_extensions(label_to_extensions, node)
                        else:
                            for next_node in non_refs:
                                self._add_extensions_chain(label_to_extensions, node, next_node)
            elif node.kind == ChangeNode.Kind.OPERATION_NODE:
                if node.sub_kind == ChangeNode.SubKind.OP_METHOD_CALL:
                    self._add_extensions(label_to_extensions, node)
                else:
                    self._magic_extension_processor(label_to_extensions, node)
            elif node.kind == ChangeNode.Kind.CONTROL_NODE:
                self._magic_extension_processor(label_to_extensions, node)

        return label_to_extensions

    @staticmethod
    def _add_extensions(label_to_exts, node):
        label = node.label
        if node.mapped:
            label += Fragment.LABEL_SEPARATOR + node.mapped.label

        s = label_to_exts.setdefault(label, set())
        s.add((node, node.mapped) if node.mapped else (node,))

    @staticmethod
    def _add_extensions_chain(label_to_exts, node, next_node):
        label = node.label
        if node.mapped:
            label += Fragment.LABEL_SEPARATOR + node.mapped.label

        label += Fragment.LABEL_SEPARATOR + next_node.label
        if next_node.mapped:
            label += Fragment.LABEL_SEPARATOR + next_node.mapped.label

        s = label_to_exts.setdefault(label, set())

        if node.mapped and next_node.mapped:
            tpl = (node, node.mapped, next_node, next_node.mapped)
        elif node.mapped:
            tpl = (node, node.mapped, next_node)
        elif next_node.mapped:
            tpl = (node, next_node, next_node.mapped)
        else:
            tpl = (node, next_node)

        s.add(tpl)

    def _magic_extension_processor(self, label_to_exts, node):  # FIXME: rename, find out in article info
        in_nodes = node.get_in_nodes()
        out_nodes = node.get_out_nodes()
        in_nodes.discard(node.mapped)
        out_nodes.discard(node.mapped)

        if in_nodes and out_nodes:
            found = False
            for n in in_nodes:
                if n in self.nodes:
                    found = True
                    break

            if found:
                found = False
                for n in out_nodes:
                    if n.sub_kind == ChangeNode.SubKind.OP_METHOD_CALL and n in self.nodes:
                        found = True
                        break

                if found:
                    self._add_extensions(label_to_exts, node)
                else:
                    for next_node in out_nodes:
                        if next_node.sub_kind == ChangeNode.SubKind.OP_METHOD_CALL:
                            self._add_extensions_chain(label_to_exts, node, next_node)
            else:
                for next_node in in_nodes:
                    self._add_extensions_chain(label_to_exts, node, next_node)

    @classmethod
    def create_groups(cls, fragments):
        groups = set()
        hash_to_fragments = cls._get_hash_to_fragments(fragments)
        for fragments in hash_to_fragments.values():
            groups = groups.union(cls._group_same_hash_fragments(fragments))
        return groups

    @classmethod
    def _group_same_hash_fragments(cls, fragments):
        fragment_groups = set()
        while len(fragments) > 0:
            fragment = next(iter(fragments))
            fragments.remove(fragment)
            new_group = cls._get_fragment_group(fragments, fragment)
            if new_group:
                fragment_groups.add(new_group)
        return fragment_groups

    @classmethod
    def _get_fragment_group(cls, fragments, fragment):
        group = [fragment]

        for curr_fragment in fragments:
            if fragment.vector.data == curr_fragment.vector.data:
                group.append(curr_fragment)

        # TODO: in the source there are also genesis fragments' groups checks
        group = cls._remove_duplicates(group)
        if len(group) >= Pattern.MIN_FREQUENCY:
            return tuple(group)

        return None

    @staticmethod
    def _remove_duplicates(group):
        if len(group) < Pattern.MIN_FREQUENCY:
            return group

        vb_utils.filter_list(
            group,
            condition=lambda i, j: group[i].is_equal(group[j])
        )
        return group

    @staticmethod
    def _get_hash_to_fragments(fragments):
        hash_to_fragments = {}
        for fragment in fragments:
            vector_hash = fragment.vector.get_hash()
            s = hash_to_fragments.setdefault(vector_hash, set())
            s.add(fragment)
        return hash_to_fragments

    def overlap(self, fragment):
        intersection = self.nodes.intersection(fragment.nodes)
        for node in intersection:
            if node.sub_kind == ChangeNode.SubKind.OP_METHOD_CALL:
                return True
        return False

    def is_equal(self, fragment):
        # TODO: the source uses idsum to optimize comparision
        return self.nodes == fragment.nodes

    def is_change(self):
        has_old = False
        has_new = False

        has_unmapped_change = False
        for node in self.nodes:
            if not has_unmapped_change and not \
                    (node.mapped and node.mapped in self.nodes and node.label == node.mapped.label):
                has_unmapped_change = True

            if node.version == Node.Version.BEFORE_CHANGES:
                has_old = True
            if node.version == Node.Version.AFTER_CHANGES:
                has_new = True
        return has_unmapped_change and has_old and has_new

    def contains(self, fragment):
        # TODO not working?
        # if self.graph != fragment.graph:
        #     return False
        return len(self.nodes) >= len(fragment.nodes) and fragment.nodes.issubset(self.nodes)


class Pattern:
    MIN_FREQUENCY = settings.get('patterns_min_frequency', 1)
    MAX_FREQUENCY = settings.get('patterns_max_frequency', 1000)

    def __init__(self, fragments, freq=None):
        self.id = None  # undefined until the pattern is not added to a miner

        self.fragments = fragments
        self.freq = freq

        self.repr = next(iter(fragments))

    @property
    def size(self):
        return len(self.repr.nodes)

    def extend(self, miner):
        label_to_fragment_to_exts = {}  # exts = set, ext = list of nodes
        for fragment in self.fragments:
            label_to_exts = fragment.get_label_to_extensions()
            for label, exts in label_to_exts.items():
                d = label_to_fragment_to_exts.setdefault(label, {})
                d[fragment] = exts

        freq_group = set()
        freq = self.MIN_FREQUENCY - 1

        for label, fragment_to_exts in label_to_fragment_to_exts.items():
            if len(fragment_to_exts) < self.MIN_FREQUENCY:
                continue

            ext_fragments = set()
            for fragment, exts in fragment_to_exts.items():
                for ext_nodes in exts:
                    ext_fragment = Fragment.create_extended(fragment, ext_nodes)
                    ext_fragments.add(ext_fragment)

            is_giant = self._is_giant_extension(ext_fragments)
            curr_group, curr_freq = self._get_most_frequent_group_and_freq(ext_fragments, is_giant)

            if curr_freq > freq:  # todo plus lattice, getting most frequent group one more time
                freq_group = curr_group
                freq = curr_freq

        if freq >= Pattern.MIN_FREQUENCY:
            extended_pattern = Pattern(freq_group, freq)
            extended_pattern.extend(miner)
        elif self.is_change():
            miner.add_pattern(self)

    def _is_giant_extension(self, ext_fragments):
        return self.size > 1 and \
               (len(ext_fragments) > Pattern.MAX_FREQUENCY or
                len(ext_fragments) > len(self.fragments) * self.size * self.size)

    def _get_most_frequent_group_and_freq(self, ext_fragments: set, is_giant):
        groups = Fragment.create_groups(ext_fragments)  # set of tuples of fragments

        freq_group = set()
        freq = self.MIN_FREQUENCY - 1

        for curr_group in groups:
            overlapped_fragments = self._get_graph_overlapped_fragments(curr_group)

            curr_group = list(curr_group)
            curr_freq = len(curr_group) - len(overlapped_fragments)

            if is_giant and self._is_giant_extension(curr_group):
                for fragment in overlapped_fragments:
                    curr_group.remove(fragment)

            if curr_freq > freq:
                freq_group = curr_group
                freq = curr_freq

        return freq_group, freq

    @staticmethod
    def _get_graph_overlapped_fragments(ext_fragments):
        """
        Return fragments, which are overlapped in a graph by other fragments.

        :param ext_fragments:
        :return:
        """
        graph_to_fragments = {}
        for fragment in ext_fragments:
            s = graph_to_fragments.setdefault(fragment.graph, list())
            s.append(fragment)

        overlapped_fragments = []
        for graph, fragments in graph_to_fragments.items():
            vb_utils.filter_list(
                fragments,
                condition=lambda i, j: fragments[i].overlap(fragments[j]),
                post_condition_fn=lambda i, j: overlapped_fragments.append(fragments[j])
            )
        return overlapped_fragments

    def _remove_overlapping_fragments(self, ext_fragments):
        pass

    def is_change(self):
        return self.repr.is_change()

    def contains(self, pattern):
        for fragment1 in self.fragments:
            for fragment2 in pattern.fragments:
                if fragment1.contains(fragment2):
                    return True
        return False
