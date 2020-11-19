import copy
import time
import multiprocessing
import functools

from typing import Set, Optional, Dict, FrozenSet, Tuple

from log import logger
from pyflowgraph.models import LinkType, Node
from changegraph.models import ChangeNode
from patterns.exas import ExasFeature, normalize
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
        logger.log(logger.DEBUG, f'Getting vector hash, data size = {len(self.data)}')

        result = 0
        for key in sorted(self.data.keys()):
            result = normalize(result * 31 + self.data[key])

        logger.log(logger.DEBUG, f'Hash calculated, value = {result}')
        return result

    def __copy__(self):
        cls = self.__class__
        o = cls.__new__(cls)
        o.data = copy.copy(self.data)
        return o


class Fragment:
    """
    Potential cloned parts in a software artifact are called fragments
    A fragment is a weakly connected sub-graph in the corresponding representation graph

    Read more: "Accurate and Efficient Structural Characteristic Feature Extraction"
    """
    LABEL_SEPARATOR = '-'
    _FRAGMENT_ID = 0

    def __init__(self):
        Fragment._FRAGMENT_ID += 1
        self.id = Fragment._FRAGMENT_ID

        self.id_sum = 0  # boosting fragment comparision todo: int overflow?

        self.parent = None
        self.graph = None
        self.nodes = []
        self.vector = CharacteristicVector()

    @property
    def size(self):
        return len(self.nodes)

    @classmethod
    def create_from_node(cls, node):
        f = Fragment()
        f.nodes.append(node)
        f.graph = node.graph

        f.id_sum = node.id

        f.__init_vector(node)

        return f

    def __init_vector(self, node):
        exas_feature = ExasFeature(nodes=[node])
        self.vector.add_feature(exas_feature.get_id_by_label(node.label))

    @classmethod
    def create_from_node_pair(cls, pair):
        f = Fragment()
        f.nodes.append(pair[0])
        f.nodes.append(pair[1])
        f.graph = pair[0].graph

        f.id_sum = pair[0].id + pair[1].id

        f.__init_vector_from_pair(pair)

        return f

    def __init_vector_from_pair(self, pair):
        exas_feature = ExasFeature(nodes=[pair[0], pair[1]])

        self.vector.add_feature(exas_feature.get_id_by_label(pair[0].label))
        self.vector.add_feature(exas_feature.get_id_by_label(pair[1].label))

        self.vector.add_feature(exas_feature.get_id_by_labels(labels=[pair[0].label, LinkType.MAP, pair[1].label]))

    @classmethod
    def create_extended(cls, fragment, ext_nodes: tuple):
        f = Fragment()
        f.parent = fragment
        f.graph = fragment.graph

        f.nodes = copy.copy(fragment.nodes)
        f.vector = copy.copy(fragment.vector)

        f.id_sum = fragment.id_sum
        for node in ext_nodes:
            f.id_sum += node.id
            f.nodes.append(node)

            logger.debug(f'Recalc vector for fragment {fragment} with node {node}', show_pid=True)
            f.__recalc_vector(node, f.nodes)

        return f

    def __recalc_vector(self, node, ext_by_one_nodes):
        exas_feature = ExasFeature(nodes=ext_by_one_nodes)
        sequence = [node.label]
        self.__exas_backward_dfs(node, node, sequence, exas_feature)

    def __exas_backward_dfs(self, first_node, last_node, sequence, exas_feature):
        logger.debug('Entering backward dfs', show_pid=True)
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
        logger.debug('Entering forward dfs', show_pid=True)
        logger.debug(f'Adding a feature for sequence: {sequence}', show_pid=True)

        feature_id = exas_feature.get_id_by_labels(sequence)
        self.vector.add_feature(feature_id)

        if len(sequence) < ExasFeature.MAX_LENGTH:
            for e in node.out_edges:
                if e.node_to in self.nodes:
                    sequence.append(e.label)
                    sequence.append(e.node_to.label)
                    self.__exas_forward_dfs(e.node_to, sequence, exas_feature)
                    del sequence[-1]
                    del sequence[-1]

    def get_label_to_ext_list(self):
        adjacent_nodes = set()
        for node in self.nodes:
            for in_node in node.get_in_nodes(excluded_labels=[LinkType.MAP]):
                if in_node not in self.nodes:
                    adjacent_nodes.add(in_node)

            for out_node in node.get_out_nodes(excluded_labels=[LinkType.MAP]):
                if out_node not in self.nodes:
                    adjacent_nodes.add(out_node)

        logger.info(f'Adjacent nodes cnt = {len(adjacent_nodes)}')

        label_to_extensions: Dict[str, Set[Tuple]] = {}
        for node in adjacent_nodes:
            if node.kind == ChangeNode.Kind.DATA_NODE:
                if node.sub_kind == ChangeNode.SubKind.DATA_LITERAL:
                    self._add_extension(label_to_extensions, node)
                else:
                    defs = node.get_definitions()
                    if not defs:
                        non_refs = node.get_out_nodes(excluded_labels=[LinkType.REFERENCE, LinkType.MAP])
                        if non_refs.intersection(set(self.nodes)):
                            self._add_extension(label_to_extensions, node)
                        else:
                            for next_node in non_refs:
                                self._add_extension_chain(label_to_extensions, node, next_node)
            elif node.kind == ChangeNode.Kind.OPERATION_NODE:
                if node.sub_kind == ChangeNode.SubKind.OP_FUNC_CALL:
                    self._add_extension(label_to_extensions, node)
                else:
                    self._add_in_out_node(label_to_extensions, node)
            elif node.kind == ChangeNode.Kind.CONTROL_NODE:
                self._add_out_node(label_to_extensions, node)

        return label_to_extensions

    @staticmethod
    def _add_extension(label_to_exts, node):
        label = node.label
        if node.mapped:
            label += Fragment.LABEL_SEPARATOR + node.mapped.label

        s = label_to_exts.setdefault(label, set())
        s.add((node, node.mapped) if node.mapped else (node,))

    @staticmethod
    def _add_extension_chain(label_to_exts, node, next_node):
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

    def _add_in_out_node(self, label_to_exts, node):
        in_nodes = node.get_in_nodes(excluded_labels=[LinkType.MAP])
        out_nodes = node.get_out_nodes(excluded_labels=[LinkType.MAP])

        if in_nodes and out_nodes:
            found = False
            for n in in_nodes:
                if n in self.nodes:
                    found = True
                    break

            if found:
                found = False
                for n in out_nodes:
                    if n in self.nodes:
                        found = True
                        break

                if found:
                    self._add_extension(label_to_exts, node)
                else:
                    for next_node in out_nodes:
                        self._add_extension_chain(label_to_exts, node, next_node)
            else:
                for next_node in in_nodes:
                    self._add_extension_chain(label_to_exts, node, next_node)

    def _add_out_node(self, label_to_exts, node):
        out_nodes = node.get_out_nodes(excluded_labels=[LinkType.MAP])
        if out_nodes.intersection(set(self.nodes)):
            self._add_extension(label_to_exts, node)

    @classmethod
    def create_groups(cls, fragments: set):
        groups: Set[FrozenSet[Fragment]] = set()

        hash_to_fragments: Dict[int, Set[Fragment]] = cls._get_hash_to_fragments(fragments)
        logger.info(f'Done hash calculations, buckets={len(hash_to_fragments.keys())}', show_pid=True)

        for key, fragments in hash_to_fragments.items():
            logger.debug(f'Bucket hash = {key}', show_pid=True)
            groups = groups.union(cls._group_same_hash_fragments(fragments))  # do grouping within calculated hash
        return groups

    @classmethod
    def _group_same_hash_fragments(cls, fragments: set):
        groups: Set[FrozenSet[Fragment]] = set()
        while len(fragments) > 0:
            fragment = next(iter(fragments))
            fragments.remove(fragment)

            group: Set[Fragment] = set()
            group.add(fragment)

            for fr in copy.copy(fragments):
                if fragment.vector.data == fr.vector.data:
                    group.add(fr)
                    fragments.remove(fr)

            # TODO: in the source there are also genesis fragments' groups checks, why?
            if len(group) >= Pattern.MIN_FREQUENCY:
                group: Set[Fragment] = cls._remove_duplicates(group)
                if len(group) >= Pattern.MIN_FREQUENCY:
                    logger.log(logger.INFO, f'A new group has been created, len = {len(group)}', show_pid=True)
                    groups.add(frozenset(group))
        return groups

    @staticmethod
    def _remove_duplicates(group):
        if len(group) < Pattern.MIN_FREQUENCY:
            return group

        lst = list(group)  # todo escape convertions
        vb_utils.filter_list(lst, condition=lambda i, j: lst[i].is_equal(lst[j]))
        logger.log(logger.INFO, f'Remove duplicates: affected {len(group) - len(lst)} items', show_pid=True)

        return set(lst)

    @staticmethod
    def _get_hash_to_fragments(fragments):
        hash_to_fragments = {}
        for fragment in fragments:
            vector_hash = fragment.vector.get_hash()
            s = hash_to_fragments.setdefault(vector_hash, set())
            s.add(fragment)
        return hash_to_fragments

    def overlap(self, fragment):
        intersection = set(self.nodes).intersection(set(fragment.nodes))  # todo: performance analysis
        for node in intersection:
            if node.sub_kind == ChangeNode.SubKind.OP_FUNC_CALL:
                return True
        return False

    def is_equal(self, fragment):
        if self.id_sum != fragment.id_sum:  # todo: performance analysis
            return False

        return set(self.nodes) == set(fragment.nodes)  # todo: performance analysis

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
        if self.id_sum < fragment.id_sum or self.size < fragment.size or self.graph.nodes != fragment.graph.nodes:
            return False

        return set(fragment.nodes).issubset(set(self.nodes))


class Pattern:
    DO_ASYNC_MINING = settings.get('patterns_async_mining', False)
    MIN_FREQUENCY = settings.get('patterns_min_frequency', 3)
    MAX_FREQUENCY = settings.get('patterns_max_frequency', 1000)

    def __init__(self, fragments, freq=None):
        self.id: Optional[int] = None  # unset until the pattern is not added to a miner

        self.fragments: Set[Fragment] = fragments
        self.freq: int = freq

        self.repr: Fragment = next(iter(fragments))

    @property
    def size(self):
        return len(self.repr.nodes)

    def extend(self, iteration=1):
        logger.warning(f'Extending pattern with fragments cnt = {len(self.fragments)}')

        start_time = time.time()
        label_to_fragment_to_ext_list: Dict[str, Dict[Fragment, Set[Tuple[Fragment]]]] = {}
        for fragment in self.fragments:
            label_to_ext_list: Dict[str, Set[Tuple]] = fragment.get_label_to_ext_list()
            for label, exts in label_to_ext_list.items():
                d = label_to_fragment_to_ext_list.setdefault(label, {})
                d[fragment] = exts

        label_to_fragment_to_ext_list = {
            k: v for k, v in label_to_fragment_to_ext_list.items()
            if len(v) >= self.MIN_FREQUENCY
        }
        logger.warning(f'Dict label_to_fragment_to_ext_list with '
                       f'{len(label_to_fragment_to_ext_list.items())} items was constructed', start_time=start_time)

        freq_group, freq = self._get_most_freq_group_and_freq(label_to_fragment_to_ext_list)

        if freq >= Pattern.MIN_FREQUENCY:
            extended_pattern = Pattern(freq_group, freq)

            new_nodes = []
            for ix in range(len(self.repr.nodes), len(extended_pattern.repr.nodes)):
                new_nodes.append(extended_pattern.repr.nodes[ix])

            old_nodes_s = '\n' + '\n'.join([f'\t{node}' for node in self.repr.nodes]) + '\n'
            new_nodes_s = '\n' + '\n'.join([f'\t{node}' for node in new_nodes]) + '\n'

            logger.info(f'Pattern with old nodes: {old_nodes_s}'
                        f'was extended with new nodes: {new_nodes_s}'
                        f'new size={extended_pattern.size}, '
                        f'fragments cnt={len(extended_pattern.fragments)}, '
                        f'iteration = {iteration}')

            return extended_pattern.extend(iteration=iteration + 1)
        else:
            logger.log(logger.WARNING, f'Done extend() for a pattern')
            return self

    def _get_most_freq_group_and_freq(self, label_to_fragment_to_ext_list):
        logger.warning(f'Processing label_to_fragment_to_ext_list to get the most freq group')
        if not label_to_fragment_to_ext_list:
            return None, -1

        start_time = time.time()

        freq_group: Set[Fragment] = set()
        freq: int = self.MIN_FREQUENCY - 1

        has_result = False
        if self.DO_ASYNC_MINING:
            try:
                with multiprocessing.Pool(processes=multiprocessing.cpu_count(), maxtasksperchild=1000) as pool:
                    fn = functools.partial(self._get_most_freq_group_and_freq_in_label,
                                           len(label_to_fragment_to_ext_list))

                    for curr_group, curr_freq in pool.imap_unordered(
                            fn, enumerate(label_to_fragment_to_ext_list.items()), chunksize=1):

                        if curr_freq > freq:  # todo plus lattice, getting most frequent group one more time
                            freq_group = curr_group
                            freq = curr_freq
                has_result = True
            except:
                logger.error('Unable to process freq groups in the async mode', exc_info=True)

        if not has_result:
            for label_num, (label, fragment_to_ext_list) in enumerate(label_to_fragment_to_ext_list.items()):
                curr_group, curr_freq = self._get_most_freq_group_and_freq_in_label(
                    len(label_to_fragment_to_ext_list), (label_num, (label, fragment_to_ext_list)))

                if curr_freq > freq:
                    freq_group = curr_group
                    freq = curr_freq

        logger.warning(f'The most freq group has freq={freq} and fr cnt={len(freq_group)}', start_time=start_time)
        return freq_group, freq

    def _get_most_freq_group_and_freq_in_label(self, labels_cnt, data):
        label_index, (label, fragment_to_ext_list) = data

        ext_fragments = set()
        for fragment, ext_list in fragment_to_ext_list.items():
            for ext in ext_list:
                ext_fragment = Fragment.create_extended(fragment, ext)
                ext_fragments.add(ext_fragment)

        logger.warning(f'Extending for label #{label}# [{1 + label_index}/{labels_cnt}] '
                       f'ext fragments = {len(ext_fragments)}', show_pid=True)

        is_giant = self._is_giant_extension(ext_fragments)

        freq_group, freq = self._get_most_freq_group_and_freq_for_fragments(ext_fragments, is_giant)
        logger.info(f'Got freq_group for label, freq={freq}, len={len(freq_group)}', show_pid=True)
        return freq_group, freq

    def _is_giant_extension(self, ext_fragments):
        return self.size > 1 and \
               (len(ext_fragments) > Pattern.MAX_FREQUENCY or
                len(ext_fragments) > len(self.fragments) * self.size * self.size)

    def _get_most_freq_group_and_freq_for_fragments(self, ext_fragments: set, is_giant):
        start = time.time()
        groups: Set[FrozenSet[Fragment]] = Fragment.create_groups(ext_fragments)
        logger.log(logger.INFO, f'Groups for {len(ext_fragments)} fragments created', start_time=start, show_pid=True)

        freq_group: Set[Fragment] = set()
        freq = self.MIN_FREQUENCY - 1

        for curr_group in groups:
            overlapped_fragments: list = self.get_graph_overlapped_fragments(curr_group)
            curr_freq = len(curr_group) - len(overlapped_fragments)

            if curr_freq > freq:
                curr_group = set(curr_group)
                if is_giant and self._is_giant_extension(curr_group):
                    for fragment in overlapped_fragments:
                        curr_group.remove(fragment)

                freq_group = curr_group
                freq = curr_freq

        return freq_group, freq

    @staticmethod
    def get_graph_overlapped_fragments(ext_fragments: frozenset):
        """
        Return fragments, which are overlapped in a graph by other fragments.
        """
        graph_to_fragments = {}
        for fragment in ext_fragments:
            s = graph_to_fragments.setdefault(fragment.graph, [])
            s.append(fragment)

        overlapped_fragments = []
        for graph, fragments in graph_to_fragments.items():
            vb_utils.filter_list(
                fragments,
                condition=lambda i, j: fragments[i].overlap(fragments[j]),
                post_condition_fn=lambda i, j: overlapped_fragments.append(fragments[j])
            )
        return overlapped_fragments

    def is_change(self):
        return self.repr.is_change()

    def contains(self, pattern):
        if self.size < pattern.size:
            return False

        for fragment2 in pattern.fragments:
            if self.size < fragment2.size:
                continue

            for fragment1 in self.fragments:
                if fragment1.contains(fragment2):
                    return True
        return False
