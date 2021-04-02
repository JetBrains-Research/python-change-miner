import os
import re
import shutil
import hashlib
import multiprocessing
import multiprocessing.pool
import functools
import copy
import html
import json
import datetime

import settings
import changegraph
from log import logger
from changegraph.models import ChangeNode
from patterns.models import Fragment, Pattern


class Miner:
    OUTPUT_DIR = settings.get('patterns_output_dir')
    OUTPUT_DETAILS = settings.get('patterns_output_details')
    FULL_PRINT = settings.get('patterns_full_print', False)
    HIDE_OVERLAPPED_FRAGMENTS = settings.get('patterns_hide_overlapped_fragments', True)

    ID_OFFSET = settings.get('patterns_id_offset', 0)
    MIN_PATTERN_SIZE = settings.get('patterns_min_size', 3)

    MIN_DATE = None
    if settings.get('patterns_min_date', required=False):
        MIN_DATE = datetime.datetime.strptime(settings.get('patterns_min_date', required=False), '%d.%m.%Y') \
            .replace(tzinfo=datetime.timezone.utc)

    def __init__(self):
        self._size_to_patterns = {}
        self._patterns_cnt = 0

    def add_pattern(self, pattern):
        self._patterns_cnt += 1
        pattern.id = self._patterns_cnt + self.ID_OFFSET

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
            if self.MIN_DATE and graph.repo_info.commit_dtm < self.MIN_DATE:
                continue

            for node in graph.nodes:
                if node.version != ChangeNode.Version.BEFORE_CHANGES or not node.mapped:
                    continue

                if not (node.kind == ChangeNode.Kind.OPERATION_NODE
                        and node.sub_kind == ChangeNode.SubKind.OP_FUNC_CALL):
                    # or node.kind == ChangeNode.Kind.CONTROL_NODE):
                    continue

                label = f'{node.label}~{node.mapped.label}'
                arr = label_to_node_pairs.setdefault(label, [])
                arr.append((node, node.mapped))

        logger.warning(f'Total pairs after the first step = {len(label_to_node_pairs.values())}')

        for num, pairs in enumerate(label_to_node_pairs.values()):
            logger.warning(f'Looking at node pair #{num + 1}')

            if len(pairs) < Pattern.MIN_FREQUENCY:
                logger.warning('Skipping...')
                continue

            fragments = set([Fragment.create_from_node_pair(pair) for pair in pairs])
            pattern = Pattern(fragments, len(fragments))
            pattern = pattern.extend()

            if pattern.is_change() and pattern.size >= self.MIN_PATTERN_SIZE:
                self.add_pattern(pattern)
                logger.warning(f'Pattern #{pattern.id} with size {pattern.size} was added')

            logger.warning(f'Done looking at node pair #{num + 1}')

        logger.warning(f'Done patterns\' mining, total count = {self._patterns_cnt}')

        self._filter_patterns()
        logger.warning(f'Done filtering, total count = {self._patterns_cnt}')

        if self.HIDE_OVERLAPPED_FRAGMENTS:
            logger.info('Removing overlapped fragments from patterns')
            for patterns in self._size_to_patterns.values():
                for pattern in patterns:
                    overlapped_fragments = Pattern.get_graph_overlapped_fragments(pattern.fragments)
                    for fragment in overlapped_fragments:
                        pattern.fragments.remove(fragment)
            logger.info('Done removing overlapped fragments from patterns')

    def _filter_patterns(self):
        keys = sorted(self._size_to_patterns.keys())
        cleared_keys = set()

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
                            if not patterns:
                                cleared_keys.add(size1)
                            found = True
                            break

                    if found:
                        break

        for k in cleared_keys:
            self._size_to_patterns.pop(k)

    def print_patterns(self):
        if not self._size_to_patterns:
            logger.warning('No patterns were found')
            return

        if os.path.exists(self.OUTPUT_DIR):
            shutil.rmtree(self.OUTPUT_DIR)

        with multiprocessing.pool.ThreadPool(processes=multiprocessing.cpu_count()) as thread_pool:
            for size, patterns in self._size_to_patterns.items():
                if not patterns:
                    continue

                logger.log(logger.WARNING, f'Exporting patterns of size {size}', show_pid=True)

                same_size_dir = os.path.join(self.OUTPUT_DIR, str(size))
                os.makedirs(same_size_dir, exist_ok=True)

                fn = functools.partial(self._print_pattern, same_size_dir)
                thread_pool.map(fn, patterns)

                self._generate_contents(
                    same_size_dir,
                    f'Size {size} contents',
                    [{'name': f'Pattern #{p.id}', 'url': f'{p.id}/details.html'}
                     for p in sorted(patterns, key=lambda p: p.id)],
                    styles='../../styles.css', has_upper_contents=True)

            self._generate_contents(
                self.OUTPUT_DIR,
                'Contents',
                [{'name': f'Size {size}', 'url': f'{size}/contents.html'}
                 for size in sorted(self._size_to_patterns.keys())])

        logger.warning('Done patterns output')

    @staticmethod
    def _generate_contents(dir, title, items, styles='../styles.css', has_upper_contents=False):
        items_list = ''
        for item in items:
            items_list += f'<a class="item" href="{item["url"]}">{item["name"]}</a>\n'

        before_items = ''
        if has_upper_contents:
            before_items = f'<a href="../contents.html">...</a><br><br>\n'

        markup = f'<html lang="en">\n' \
                 f'<head>\n' \
                 f'<title>{title}</title>\n' \
                 f'<link rel="stylesheet" href="{styles}">\n' \
                 f'</head>\n' \
                 f'<body>\n' \
                 f'{before_items}{items_list}' \
                 f'</body>\n' \
                 f'</html>'

        with open(os.path.join(dir, 'contents.html'), 'w+') as f:
            f.write(markup)

    @classmethod
    def _print_pattern(cls, root_dir, pattern):
        logger.warning(f'Printing pattern #{pattern.id}', show_pid=True)

        pattern_id_dir = os.path.join(root_dir, str(pattern.id))
        os.makedirs(pattern_id_dir, exist_ok=True)

        details = cls._generate_html_details(pattern)
        with open(os.path.join(pattern_id_dir, 'details.html'), 'w+') as f:
            f.write(details)

        printable_fragments = pattern.fragments if cls.FULL_PRINT else [pattern.repr]
        for fragment in printable_fragments:
            try:
                cls._print_fragment(pattern, pattern_id_dir, fragment)
            except:
                logger.error(f'Unable to print fragment {fragment.id} for pattern {pattern.id}, '
                             f'commit=#{fragment.graph.repo_info.commit_hash}, '
                             f'file={fragment.graph.repo_info.old_method.file_path}, '
                             f'method={fragment.graph.repo_info.old_method.full_name}', exc_info=True)

    @classmethod
    def _print_fragment(cls, pattern, out_dir, fragment):
        file_suffix = f'-{fragment.id}' if cls.FULL_PRINT else ''
        changegraph.print_out_nodes(fragment.nodes, path=os.path.join(out_dir, f'fragment{file_suffix}.dot'))
        changegraph.export_graph_image(fragment.graph, path=os.path.join(out_dir, f'graph{file_suffix}.dot'))

        sample = cls._generate_html_sample(f'{pattern.id}{file_suffix}', fragment)
        if sample:
            with open(os.path.join(out_dir, f'sample{file_suffix}.html'), 'w+') as f:
                f.write(sample)

            if not cls.OUTPUT_DETAILS:
                return

            repo_info = fragment.graph.repo_info
            with open(os.path.join(out_dir, f'sample-details{file_suffix}.json'), 'w+') as f:
                data = {
                    'author': {
                        'email': repo_info.author_email,
                        'name': repo_info.author_name
                    },
                    'repo': {
                        'name': repo_info.repo_name,
                        'path': str(repo_info.repo_path),
                        'url': repo_info.repo_url
                    },
                    'commit': {
                        'hash': repo_info.commit_hash,
                        'dtm': repo_info.commit_dtm.strftime(
                            '%d.%m.%Y %H:%M:%S') if repo_info.commit_dtm else None
                    },
                    'files': {
                        'old': {
                            'path': repo_info.old_file_path
                        },
                        'new': {
                            'path': repo_info.new_file_path,
                        }
                    },
                    'methods': {
                        'old': {
                            'name': repo_info.old_method.name,
                            'full_name': repo_info.old_method.full_name
                        },
                        'new': {
                            'name': repo_info.new_method.name,
                            'full_name': repo_info.new_method.full_name
                        }
                    }
                }
                json.dump(data, f, indent=4)

    @classmethod
    def _generate_html_details(cls, pattern):
        instances = []
        for fragment in pattern.fragments:
            instances.append(cls._generate_html_instance(fragment, is_repr=fragment == pattern.repr))

        inner = f''
        if not cls.FULL_PRINT:
            inner += f'<div><a href="sample.html">Sample</a></div>\n' \
                     f'<div><a target="_blank" href="fragment.dot.pdf">Fragment</a></div>\n' \
                     f'<div><a target="_blank" href="graph.dot.pdf">Change graph</a></div><br>\n'

        instance_separator = '<br>\n\n'
        details = f'<html lang="en">\n' \
                  f'<head>\n' \
                  f'<title>Details {pattern.id}\n</title>' \
                  f'<link rel="stylesheet" href="../../../styles.css">\n' \
                  f'<script type="text/javascript" src="../../../libs/jquery.js"></script>\n' \
                  f'<script type="text/javascript" src="../../../general.js"></script>\n' \
                  f'</head>\n' \
                  f'<body>\n' \
                  f'<a href="../contents.html">...</a><br><br>\n' \
                  f'<div>Frequency: {pattern.freq}</div>\n' \
                  f'Pattern ID: <span data-target="copy">{pattern.id}</span>\n' \
                  f'<span class="copy-icon" data-action="copy">&#x2398;</span>\n' \
                  f'<br>\n' \
                  f'{inner}\n' \
                  f'<h2>Instances:</h2>\n' \
                  f'{instance_separator.join(instances)}' \
                  f'</body>\n' \
                  f'</html>\n'
        return details

    @classmethod
    def _generate_html_instance(cls, fragment, is_repr=False):
        repo_info = fragment.graph.repo_info
        repo_name = repo_info.repo_name
        repo_url = repo_info.repo_url.strip()[:-4]
        commit_hash = repo_info.commit_hash

        line_number = repo_info.old_method.ast.lineno

        optional_links = ''
        if cls.FULL_PRINT:
            suffix = f'-{fragment.id}'
            optional_links = f'<div><a href="sample{suffix}.html">Sample{suffix}</a></div>\n' \
                             f'<div><a target="_blank" href="fragment{suffix}.dot.pdf">Fragment{suffix}</a></div>\n' \
                             f'<div><a target="_blank" href="graph{suffix}.dot.pdf">Graph{suffix}</a></div>\n'

        result = f'<div class="pattern-instance{" pattern-repr" if is_repr else ""}">\n' \
                 f'<div>Repo: <a target="_blank" href="{repo_url}">{repo_name}</a></div>\n' \
                 f'<div>Commit: <a target="_blank" href="{repo_url}/commit/{commit_hash}">#{commit_hash}</a></div>\n' \
                 f'<div>File: {repo_info.old_method.file_path} to {repo_info.new_method.file_path}</div>\n' \
                 f'<div>Func: {repo_info.old_method.full_name} to {repo_info.new_method.full_name}</div>\n' \
                 f'<div>Link: ' \
                 f'<a target="_blank" href="' \
                 f'{cls._get_base_line_url(repo_info, version=ChangeNode.Version.BEFORE_CHANGES)}{line_number}">' \
                 f'open [{line_number}]' \
                 f'</a>' \
                 f'</div>\n' \
                 f'{optional_links}' \
                 f'</div>\n'
        return result

    @staticmethod
    def _get_base_line_url(repo_info, version):
        repo_url = repo_info.repo_url.strip()[:-4]
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
                 f'<link rel="stylesheet" href="../../../libs/highlight/default.css">\n' \
                 f'<link rel="stylesheet" href="../../../styles.css">\n' \
                 f'<script type="text/javascript" src="../../../libs/highlight/highlight.pack.js"></script>\n' \
                 f'<script type="text/javascript" src="../../../libs/jquery.js"></script>\n' \
                 f'<script type="text/javascript" src="../../../libs/underscore.js"></script>\n' \
                 f'<script type="text/javascript" src="../../../general.js"></script>\n' \
                 f'<script type="text/javascript" src="../../../sample.js"></script>\n' \
                 f'</head>\n' \
                 f'<body>\n' \
                 f'<div id="repo">' \
                 f'<div><a href="details.html">Details</a></div><br>\n' \
                 f'<span id="sample_id">Sample ID: <span data-target="copy">{sample_id}</span></span>\n' \
                 f'<span class="copy-icon" data-action="copy">&#x2398;</span>\n' \
                 f'<div><span class="title" data-action="visibility">More info</span>\n' \
                 f'<div data-target="visibility">\n' \
                 f'<br>\n' \
                 f'Repository: {repo_info.repo_name}<br>\n' \
                 f'File (old): {repo_info.old_method.file_path}</div></div>\n' \
                 f'<div id="commit_hash">Commit: {repo_info.commit_hash}</div>\n' \
                 f'<div id="before_code_block">\n' \
                 f'<div class="title">Before changes:</div>\n' \
                 f'<div class="expand-btn" data-action="toggle-expand" data-kind="top" ' \
                 f'data-code-version="{ChangeNode.Version.BEFORE_CHANGES}"> </div>\n' \
                 f'{cls._generate_pre_html(fragment, repo_info, old_src, ChangeNode.Version.BEFORE_CHANGES)}' \
                 f'<div class="expand-btn" data-action="toggle-expand" data-kind="bottom" ' \
                 f'data-code-version="{ChangeNode.Version.BEFORE_CHANGES}"> </div>\n' \
                 f'</div>\n' \
                 f'<div id="after_code_block">\n' \
                 f'<div class="title">After changes:</div>\n' \
                 f'<div class="expand-btn" data-action="toggle-expand" data-kind="top" ' \
                 f'data-code-version="{ChangeNode.Version.AFTER_CHANGES}"> </div>\n' \
                 f'{cls._generate_pre_html(fragment, repo_info, new_src, ChangeNode.Version.AFTER_CHANGES)}' \
                 f'<div class="expand-btn" data-action="toggle-expand" data-kind="bottom" ' \
                 f'data-code-version="{ChangeNode.Version.AFTER_CHANGES}"> </div>\n' \
                 f'</div>\n' \
                 f'</div>\n' \
                 f'</body>\n' \
                 f'</html>\n'
        return sample

    @classmethod
    def _generate_pre_html(cls, fragment, repo_info, src, version):
        method = repo_info.old_method if version == ChangeNode.Version.BEFORE_CHANGES else repo_info.new_method

        return f'<pre class="code language-python" ' \
               f'data-base-line-url="{cls._get_base_line_url(repo_info, version)}" ' \
               f'data-line-number="{method.ast.lineno}" ' \
               f'data-code-version="{version}">\n' \
               f'{cls._get_markup(fragment, src, version)}' \
               f'</pre>\n'

    @classmethod
    def _get_markup(cls, fragment, src, version):
        printable_nodes = set()
        for node in fragment.nodes:
            in_nodes = node.get_in_nodes()
            for in_node in in_nodes:
                defs = in_node.get_definitions()
                for def_node in defs:
                    if def_node in fragment.nodes:
                        printable_nodes.add(in_node)
                        break
        printable_nodes = printable_nodes.union(fragment.nodes)

        pattern_intervals = []
        for node in printable_nodes:
            if node.version != version:
                continue

            intervals = node.get_property(ChangeNode.Property.SYNTAX_TOKEN_INTERVALS)
            if intervals is not None:
                for interval in intervals:
                    pattern_intervals.append(interval)
                continue

            start = node.ast.first_token.startpos
            end = node.ast.last_token.endpos
            pattern_intervals.append([start, end])

        pattern_intervals = cls.merge_intervals(pattern_intervals)

        markup = src
        offset = 0
        last_end = 0

        for start, end in pattern_intervals:
            start += offset
            end += offset

            escaped_markup = markup[:last_end] + html.escape(markup[last_end:start]) + markup[start:]
            offset_delta = len(escaped_markup) - len(markup)
            markup = escaped_markup

            start += offset_delta
            end += offset_delta
            offset += offset_delta

            chunk, offset_delta = cls._get_highlighted_chunk(markup[start:end])
            markup = markup[:start] + chunk + markup[end:]

            offset += offset_delta
            last_end = end + offset_delta

        markup = markup[:last_end] + html.escape(markup[last_end:])

        return markup.strip()

    @staticmethod
    def _get_highlighted_chunk(chunk_src):
        # escape
        chunk = html.escape(chunk_src)
        offset = len(chunk) - len(chunk_src)

        # mark changes
        put_before = f'<span class="highlighted">'
        put_after = f'</span>'
        highlight_offset = (len(put_before) + len(put_after))

        line_break_regex = re.compile('\n')
        lb_repl_cnt = 0

        def line_break_repl(_):
            nonlocal lb_repl_cnt
            lb_repl_cnt += 1
            return f'{put_after}\n{put_before}'

        chunk = re.sub(line_break_regex, line_break_repl, chunk)
        offset += lb_repl_cnt * highlight_offset

        chunk = put_before + chunk + put_after
        offset += highlight_offset

        return chunk, offset

    @staticmethod
    def merge_intervals(intervals):
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
