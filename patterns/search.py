import os
import re
import shutil
import hashlib
import multiprocessing
import multiprocessing.pool
import functools
import copy

import settings
import changegraph
from log import logger
from changegraph.models import ChangeNode
from patterns.models import Fragment, Pattern


class Miner:
    OUTPUT_DIR = settings.get('patterns_output_dir')

    def __init__(self):
        self._size_to_patterns = {}
        self._patterns_cnt = 0

    def add_pattern(self, pattern):
        self._patterns_cnt += 1
        pattern.id = self._patterns_cnt

        patterns = self._size_to_patterns.setdefault(pattern.size, set())
        patterns.add(pattern)

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
                if node.version != ChangeNode.Version.BEFORE_CHANGES or not node.mapped:
                    continue

                if node.kind != ChangeNode.Kind.OPERATION_NODE or node.sub_kind != ChangeNode.SubKind.OP_METHOD_CALL:
                    continue

                label = f'{node.label}~{node.mapped.label}'
                arr = label_to_node_pairs.setdefault(label, [])
                arr.append((node, node.mapped))

        logger.warning(f'Total pairs after the first step = {len(label_to_node_pairs.values())}')

        for num, pairs in enumerate(label_to_node_pairs.values()):
            logger.warning(f'Looking at node pair #{num+1}')

            if len(pairs) < Pattern.MIN_FREQUENCY:
                logger.warning('Skipping...')
                continue

            fragments = set([Fragment.create_from_node_pair(pair) for pair in pairs])
            pattern = Pattern(fragments, len(fragments))
            pattern = pattern.extend()

            if pattern:
                self.add_pattern(pattern)
                logger.warning(f'Pattern #{pattern.id} with size {pattern.size} was added')

            logger.warning(f'Done looking at node pair #{num+1}')

        logger.warning(f'Done patterns\' mining, total count = {self._patterns_cnt}')

        self._filter_patterns()
        logger.warning(f'Done filtering, total count = {self._patterns_cnt}')

    def _filter_patterns(self):
        keys = sorted(self._size_to_patterns.keys())

        for size1 in keys:
            patterns = self._size_to_patterns[size1]

            for pattern1 in copy.copy(patterns):
                for size2 in keys:
                    if size1 > size2:
                        continue

                    patterns2 = self._size_to_patterns[size2]
                    found = False

                    for pattern2 in patterns2:
                        if pattern2 != pattern1 and pattern2.contains(pattern1):
                            patterns.remove(pattern1)
                            self._patterns_cnt -= 1
                            found = True
                            break

                    if found:
                        break

    def print_patterns(self):  # todo: arrange patterns by their frequency
        if not self._size_to_patterns:
            logger.warning('No patterns were found')
            return

        if os.path.exists(self.OUTPUT_DIR):
            shutil.rmtree(self.OUTPUT_DIR)

        with multiprocessing.pool.ThreadPool(processes=multiprocessing.cpu_count()) as thread_pool:
            for patterns in self._size_to_patterns.values():
                if not patterns:
                    continue

                size = next(iter(patterns)).size
                logger.log(logger.WARNING, f'Exporting patterns of size {size}', show_pid=True)

                same_size_dir = os.path.join(self.OUTPUT_DIR, str(size))
                os.makedirs(same_size_dir, exist_ok=True)

                fn = functools.partial(self._print_pattern, same_size_dir)
                thread_pool.map(fn, patterns)

                self._generate_contents(
                    same_size_dir,
                    f'Size {same_size_dir} contents',
                    [{'name': f'Pattern #{p.id}', 'url': f'{p.id}/details.html'} for p in patterns],
                    styles='../../styles.css')

            self._generate_contents(
                self.OUTPUT_DIR,
                'Contents',
                [{'name': f'Size {size}', 'url': f'{size}/contents.html'} for size in self._size_to_patterns.keys()])

    @staticmethod
    def _generate_contents(dir, title, items, styles='../styles.css'):
        items_list = ''
        for item in items:
            items_list += f'<a class="item" href="{item["url"]}">{item["name"]}</a>\n'

        markup = f'<html lang="en">\n' \
                 f'<head>\n' \
                 f'<title>{title}</title>\n' \
                 f'<link rel="stylesheet" href="{styles}">\n' \
                 f'</head>\n' \
                 f'<body>\n' \
                 f'{items_list}' \
                 f'</body>\n' \
                 f'</html>'

        with open(os.path.join(dir, 'contents.html'), 'w+') as f:
            f.write(markup)

    def _print_pattern(self, root_dir, pattern):
        logger.warning(f'Printing pattern #{pattern.id}', show_pid=True)

        pattern_id_dir = os.path.join(root_dir, str(pattern.id))
        os.makedirs(pattern_id_dir, exist_ok=True)

        changegraph.export_graph_image(pattern.repr.graph, path=os.path.join(pattern_id_dir, 'graph.dot'))
        changegraph.print_out_nodes(pattern.repr.nodes, path=os.path.join(pattern_id_dir, 'fragment.dot'))

        sample = self._generate_html_sample(pattern.id, pattern.repr)
        if sample:
            with open(os.path.join(pattern_id_dir, 'sample.html'), 'w+') as f:
                f.write(sample)

        details = self._generate_html_details(pattern)
        with open(os.path.join(pattern_id_dir, 'details.html'), 'w+') as f:
            f.write(details)

    @classmethod
    def _generate_html_details(cls, pattern):
        instances = []
        for fragment in pattern.fragments:
            instances.append(cls._generate_html_instance(fragment))

        instance_separator = '<br>\n\n'
        details = f'<html lang="en">\n' \
                  f'<head>\n' \
                  f'<title>Details {pattern.id}\n</title>' \
                  f'<link rel="stylesheet" href="../../../styles.css">\n' \
                  f'</head>\n' \
                  f'<body>\n' \
                  f'<div><a href="sample.html">Sample</a></div>\n' \
                  f'<div><a target="_blank" href="fragment.dot.pdf">Fragment</a></div>\n' \
                  f'<div><a target="_blank" href="graph.dot.pdf">Change graph</a></div>\n' \
                  f'<br><div>Frequency: {pattern.freq}</div>\n' \
                  f'<h2>Instances:</h2>\n' \
                  f'{instance_separator.join(instances)}' \
                  f'</body>\n' \
                  f'</html>\n'
        return details

    @classmethod
    def _generate_html_instance(cls, fragment):
        repo_info = fragment.graph.repo_info
        repo_name = repo_info.repo_name
        repo_url = repo_info.repo_url.strip('.git')
        commit_hash = repo_info.commit_hash

        line_number = repo_info.old_method.ast.lineno

        result = f'<div class="pattern-instance">\n' \
                 f'<div>Repo: <a target="_blank" href="{repo_url}">{repo_name}</a></div>\n' \
                 f'<div>Commit: <a target="_blank" href="{repo_url}/commit/{commit_hash}">#{commit_hash}</a></div>\n' \
                 f'<div>Link: ' \
                 f'<a target="_blank" href="' \
                 f'{cls._get_base_line_url(repo_info, version=ChangeNode.Version.BEFORE_CHANGES)}{line_number}">' \
                 f'open [{line_number}]' \
                 f'</a>' \
                 f'</div>\n' \
                 f'</div>\n'
        return result

    @staticmethod
    def _get_base_line_url(repo_info, version):
        repo_url = repo_info.repo_url.strip('.git')
        commit_hash = repo_info.commit_hash

        if version == ChangeNode.Version.BEFORE_CHANGES:
            method = repo_info.old_method
            postfix = 'L'
        else:
            method = repo_info.new_method
            postfix = 'R'

        m = hashlib.md5()
        m.update(method.file_path.encode('utf-8'))
        file_path_md5 = m.hexdigest()

        return f'{repo_url}/commit/{commit_hash}#diff-{file_path_md5}{postfix}'

    @classmethod
    def _generate_html_sample(cls, sample_id, fragment):
        repo_info = fragment.graph.repo_info
        old_src = repo_info.old_method.get_source()
        new_src = repo_info.new_method.get_source()

        if not old_src:
            logger.info(f'Unable to get source from ast {repo_info.old_method.ast}')
            return None
        if not new_src:
            logger.warning(f'Unable to get source from ast {repo_info.new_method.ast}')
            return None

        sample = f'<html lang="en">\n' \
                 f'<head>\n' \
                 f'<title>Sample {sample_id}</title>\n' \
                 f'<link rel="stylesheet" href="../../../styles.css">\n' \
                 f'<script type="text/javascript" src="../../../libs/jquery.js"></script>\n' \
                 f'<script type="text/javascript" src="../../../libs/underscore.js"></script>\n' \
                 f'<script type="text/javascript" src="../../../sample.js"></script>\n' \
                 f'</head>\n' \
                 f'<body>\n' \
                 f'<div id="repo">' \
                 f'<div><a href="details.html">Details</a></div><br>\n' \
                 f'Repository: {repo_info.repo_name}<br>\n' \
                 f'File (old): {repo_info.old_method.file_path}\n' \
                 f'<div id="commit_hash">Commit: {repo_info.commit_hash}</div>\n' \
                 f'<div id="before_code_block">\n' \
                 f'<div class="title">Before changes:</div>\n' \
                 f'{cls._generate_pre_html(fragment, repo_info, old_src, ChangeNode.Version.BEFORE_CHANGES)}' \
                 f'</div>\n' \
                 f'<div id="after_code_block">\n' \
                 f'<div class="title">After changes:</div>\n' \
                 f'{cls._generate_pre_html(fragment, repo_info, new_src, ChangeNode.Version.AFTER_CHANGES)}' \
                 f'</div>\n' \
                 f'</div>\n' \
                 f'</body>\n' \
                 f'</html>\n'
        return sample

    @classmethod
    def _generate_pre_html(cls, fragment, repo_info, src, version):
        method = repo_info.old_method if version == ChangeNode.Version.BEFORE_CHANGES else repo_info.new_method

        return f'<pre class="code" ' \
               f'data-base-line-url="{cls._get_base_line_url(repo_info, version)}" ' \
               f'data-line-number="{method.ast.lineno}">\n' \
               f'{cls._get_markup(fragment, src, version)}' \
               f'</pre>\n'

    @classmethod
    def _get_markup(cls, fragment, src, version):
        pattern_intervals = []
        for node in fragment.nodes:
            if node.version != version:
                continue

            if getattr(node, '_data', None):  # TODO: remove later, added for backward comp
                intervals = node.get_property(ChangeNode.Property.SYNTAX_TOKEN_INTERVALS, [])
                if intervals:
                    for interval in intervals:
                        pattern_intervals.append(interval)
                    continue

            # todo: resolve if-else in other place?
            if node.kind == ChangeNode.Kind.OPERATION_NODE and node.sub_kind == ChangeNode.SubKind.OP_METHOD_CALL:
                start = node.ast.func.first_token.startpos
                end = node.ast.func.last_token.endpos
            else:
                start = node.ast.first_token.startpos
                end = node.ast.last_token.endpos
            pattern_intervals.append([start, end])

        pattern_intervals = cls._merge_intervals(pattern_intervals)

        markup = src
        offset = 0

        put_before = f'<span class="highlighted">'
        put_after = f'</span>'
        offset_len = len(put_before) + len(put_after)

        line_break_regex = re.compile('\n')

        for start, end in pattern_intervals:
            start += offset
            end += offset

            chunk = markup[start:end]
            lb_repl_cnt = 0

            def line_break_repl(_):
                nonlocal lb_repl_cnt
                lb_repl_cnt += 1
                return f'{put_after}\n{put_before}'

            chunk = re.sub(line_break_regex, line_break_repl, chunk)
            offset += offset_len*lb_repl_cnt

            markup = markup[:start] + put_before + chunk + put_after + markup[end:]
            offset += offset_len

        return markup.strip()

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
                last_interval[1] = max(last_end, end)
            else:
                new_intervals.append(intervals[i])
                last_interval = intervals[i]

        return new_intervals
