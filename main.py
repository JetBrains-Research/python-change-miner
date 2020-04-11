import ast
import os
import pickle
import sys
import stackimpact
import datetime
import argparse
import multiprocessing

from log import logger
from patterns import Miner
from patterns.models import Fragment, Pattern
from vcs.traverse import GitAnalyzer, RepoInfo, Method

import pyflowgraph
import changegraph
import settings


class RunModes:
    BUILD_PY_FLOW_GRAPH = 'pfg'
    BUILD_CHANGE_GRAPH = 'cg'
    COLLECT_CHANGE_GRAPHS = 'collect-cgs'
    MINE_PATTERNS = 'patterns'

    ALL = [BUILD_PY_FLOW_GRAPH, BUILD_CHANGE_GRAPH, COLLECT_CHANGE_GRAPHS, MINE_PATTERNS]


def main():
    logger.info('------------------------------ Starting ------------------------------')

    if settings.get('use_stackimpact', required=False):
        _ = stackimpact.start(
            agent_key=settings.get('stackimpact_agent_key'),
            app_name='CodeChangesMiner',
            debug=True,
            app_version=str(datetime.datetime.now())
        )

    sys.setrecursionlimit(2**31-1)
    multiprocessing.set_start_method('spawn', force=True)

    parser = argparse.ArgumentParser()
    parser.add_argument('mode', help=f'One of {RunModes.ALL}', type=str)
    args, _ = parser.parse_known_args()

    current_mode = args.mode

    if current_mode == RunModes.BUILD_PY_FLOW_GRAPH:
        parser.add_argument('-i', '--input', help='Path to source code file', type=str, required=True)
        parser.add_argument('-o', '--output', help='Path to output file', type=str, default='pyflowgraph.dot')
        parser.add_argument('--no-closure', action='store_true')
        parser.add_argument('--show-deps', action='store_true')
        args = parser.parse_args()

        fg = pyflowgraph.build_from_file(
            args.input, show_dependencies=args.show_deps, build_closure=not args.no_closure)
        pyflowgraph.export_graph_image(fg, args.output)
    elif current_mode == RunModes.BUILD_CHANGE_GRAPH:
        parser.add_argument('-s', '--src', help='Path to source code before changes', type=str, required=True)
        parser.add_argument('-d', '--dest', help='Path to source code after changes', type=str, required=True)
        parser.add_argument('-o', '--output', help='Path to output file', type=str, default='changegraph.dot')
        args = parser.parse_args()

        fg = changegraph.build_from_files(args.src, args.dest)
        changegraph.export_graph_image(fg, args.output)
    elif current_mode == RunModes.COLLECT_CHANGE_GRAPHS:
        GitAnalyzer().build_change_graphs()
    elif current_mode == RunModes.MINE_PATTERNS:
        parser.add_argument('-s', '--src', help='Path to source code before changes', type=str, nargs='+')
        parser.add_argument('-d', '--dest', help='Path to source code after changes', type=str, nargs='+')
        parser.add_argument('--fake-mining', action='store_true')
        args = parser.parse_args()

        if args.src or args.dest or args.fake_mining:
            if not args.src or len(args.src) != len(args.dest):
                raise ValueError('src and dest have different size or unset')

            change_graphs = []
            for old_path, new_path in zip(args.src, args.dest):
                methods = []
                for n, path in enumerate([old_path, new_path]):
                    with open(path, 'r+') as f:
                        src = f.read()
                        methods.append(Method(path, 'test_name', ast.parse(src, mode='exec').body[0], src))

                repo_info = RepoInfo('mock repo path', 'mock repo name', 'mock repo url', 'mock hash',
                                     methods[0], methods[1])

                cg = changegraph.build_from_files(old_path, new_path, repo_info=repo_info)
                change_graphs.append(cg)

            miner = Miner()
            if args.fake_mining:
                for cg in change_graphs:
                    fragment = Fragment()
                    fragment.graph = cg
                    fragment.nodes = cg.nodes
                    pattern = Pattern([fragment])
                    miner.add_pattern(pattern)
            else:
                miner.mine_patterns(change_graphs)
            miner.print_patterns()
        else:
            storage_dir = settings.get('change_graphs_storage_dir')
            file_names = os.listdir(storage_dir)

            logger.warning(f'Found {len(file_names)} files in storage directory')

            change_graphs = []
            for file_num, file_name in enumerate(file_names):
                file_path = os.path.join(storage_dir, file_name)
                try:
                    with open(file_path, 'rb') as f:
                        change_graphs += pickle.load(f)
                except:
                    logger.warning(f'Incorrect file {file_path}')

                if file_num % 1000 == 0:
                    logger.warning(f'Loaded [{1+file_num}/{len(file_names)}] files')
            logger.warning('Pattern mining has started')

            miner = Miner()
            try:
                miner.mine_patterns(change_graphs)
            except KeyboardInterrupt:
                logger.warning('KeyboardInterrupt: mined patterns will be stored before exit')

            miner.print_patterns()
    else:
        raise ValueError


if __name__ == '__main__':
    main()
