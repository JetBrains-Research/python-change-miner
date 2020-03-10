import os
import logging
import shutil

import changegraph
from pyflowgraph.models import Node
from patterns.models import Fragment, Pattern


class Miner:
    OUTPUT_DIR = os.path.join('output', 'patterns')

    def __init__(self):
        self._size_to_patterns = {}
        self._pattern_cnt = 0

    def add_pattern(self, pattern):
        self._pattern_cnt += 1
        pattern.id = self._pattern_cnt

        patterns = self._size_to_patterns.setdefault(pattern.size, [])
        patterns.append(pattern)

    def mine_patterns(self, change_graphs, mining_level=1):
        if mining_level == 1:
            self._mine(change_graphs)
        else:
            raise NotImplementedError

    def _mine(self, graphs):
        # TODO: delete assign nodes?
        # TODO: collapse literals?

        label_to_node_pairs = {}
        for graph in graphs:
            for node in graph.nodes:
                if node.version != Node.Version.BEFORE_CHANGES or not node.mapped:
                    continue

                label = f'{node.label}~{node.mapped.label}'
                arr = label_to_node_pairs.setdefault(label, [])
                arr.append((node, node.mapped))

        for key, pairs in label_to_node_pairs.items():
            if len(pairs) < Pattern.MIN_FREQUENCY:  # or check core action:
                continue

            fragments = set([Fragment.create_from_node_pair(pair) for pair in pairs])
            pattern = Pattern(fragments, len(fragments))
            pattern.extend(self)

        cnt = sum([len(patterns) for patterns in self._size_to_patterns.values()])
        logging.warning(f'Done patterns\' mining, total count = {cnt}')

        cnt = sum([len(patterns) for patterns in self._size_to_patterns.values()])
        logging.warning(f'Done filtering, total count = {cnt}')

    @staticmethod
    def _filter_patterns(size_to_patterns):
        return  # FIXME
        # keys = sorted(size_to_patterns.keys())
        #
        # for size1 in keys:
        #     for size2 in keys:
        #         if size1 < size2:
        #             continue
        #
        #         for p1 in copy.copy(patterns):
        #             for p2 in copy.copy(patterns2):
        #                 if p1 != p2 and p1.contains(p2):
        #                     patterns2.remove(p2)

    def print_result(self):
        if not self._size_to_patterns:
            logging.warning('No patterns were found')
            return

        if os.path.exists(self.OUTPUT_DIR):
            shutil.rmtree(self.OUTPUT_DIR)

        for patterns in self._size_to_patterns.values():
            current_dir = os.path.join(self.OUTPUT_DIR, str(patterns[0].size))
            os.makedirs(current_dir, exist_ok=True)

            for pattern in patterns:
                graph = pattern.repr.graph
                changegraph.export_graph_image(graph, path=os.path.join(current_dir, 'graph'))
                changegraph.print_out_nodes(pattern.repr.nodes, path=os.path.join(current_dir, 'fragment'))

                old_src = graph.repo_info.old_method.get_source()
                new_src = graph.repo_info.new_method.get_source()

                if not old_src:
                    logging.warning(f'Unable to get source from ast {graph.repo_info.old_method.ast}')
                    continue
                if not new_src:
                    logging.warning(f'Unable to get source from ast {graph.repo_info.new_method.ast}')
                    continue

                markup = f'' \
                         f'<html lang="en">\n' \
                         f'<head>\n' \
                         f'<title>Pattern {pattern.id}</title>\n' \
                         f'<link rel="stylesheet" href="../../styles.css">\n' \
                         f'</head>\n' \
                         f'<body>' \
                         f'<div id="repo">Repository: {graph.repo_info.repo_name}\n' \
                         f'<div id="commit_hash">Commit: {graph.repo_info.commit_hash}</div>\n' \
                         f'<div id="before_code_block">\n' \
                         f'<div class="title">Before changes:</div>\n' \
                         f'<pre class="code">\n' \
                         f'{self._get_markup(pattern, old_src, Node.Version.BEFORE_CHANGES)}\n' \
                         f'</pre>\n' \
                         f'</div>\n' \
                         f'<div id="after_code_block">\n' \
                         f'<div class="title">After changes:</div>\n' \
                         f'<pre class="code">\n' \
                         f'{self._get_markup(pattern, new_src, Node.Version.AFTER_CHANGES)}\n' \
                         f'</pre>\n' \
                         f'</div>\n' \
                         f'</body>\n' \
                         f'</html>\n'

                with open(os.path.join(current_dir, f'{pattern.id}.html'), 'w+') as f:
                    f.write(markup)

    def _get_markup(self, pattern, src, version):
        pattern_intervals = []
        for node in pattern.repr.nodes:
            if node.version != version:
                continue

            start = node.ast.first_token.startpos
            end = node.ast.last_token.endpos
            pattern_intervals.append([start, end])

            extra_tokens = node.get_property(Node.Property.EXTRA_TOKENS, [])
            for extra_token in extra_tokens:
                pattern_intervals.append([extra_token['first_token'], extra_token['last_token']])

        pattern_intervals = self._merge_intervals(pattern_intervals)

        markup = src
        offset = 0

        put_before = f'<span class="highlighted">'
        put_after = f'</span>'
        offset_len = len(put_before) + len(put_after)

        for start, end in pattern_intervals:
            start += offset
            end += offset

            markup = markup[:start] + put_before + markup[start:end] + put_after + markup[end:]
            offset += offset_len

        # markup = re.sub(r'\n', '<br>', markup)
        # markup = re.sub(r'\s\s', '<div class="tab"></div>', markup)
        return markup

    @staticmethod
    def _merge_intervals(intervals):
        new_intervals = []
        last_interval = None

        intervals = sorted(intervals)
        for i in range(len(intervals)):
            if not last_interval:
                new_intervals.append(intervals[i])
                last_interval = intervals[i]
                continue

            last_start, last_end = last_interval
            start, end = intervals[i]

            if last_end >= start:
                last_interval[1] = end
            else:
                new_intervals.append(intervals[i])
                last_interval = intervals[i]

        return new_intervals
