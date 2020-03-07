import logging
import os
import tempfile
import ast
import uuid
import pickle
import multiprocessing
import threading

from pydriller import RepositoryMining
from pydriller.domain.commit import ModificationType

import settings
import changegraph
import vb_utils


class GitAnalyzer:
    GIT_REPOSITORIES_DIR = settings.get('git_repositories_dir')
    STORE_INTERVAL = settings.get('store_interval')

    def __init__(self):
        self._pool = multiprocessing.Pool(processes=multiprocessing.cpu_count(), maxtasksperchild=1000)

    @staticmethod
    def _log(text):
        logging.warning(f'#{os.getpid()}: {text}')

    def _get_commit_change_graphs_callback(self, graphs_per_commits):
        new_change_graphs = []
        for graphs in graphs_per_commits:
            if not graphs:
                continue
            new_change_graphs += graphs

        logging.warning(f'Built {len(new_change_graphs)} change graphs')

        if not new_change_graphs:
            return

        self._async_store_change_graphs(new_change_graphs)

    def build_change_graphs(self):
        for repo_name in os.listdir(self.GIT_REPOSITORIES_DIR):
            if repo_name.startswith('_'):
                logging.warning(f'Skipping repository with name={repo_name}')
                continue

            logging.warning(f'Looking at {repo_name}')

            repo_path = os.path.join(self.GIT_REPOSITORIES_DIR, repo_name)
            repo = RepositoryMining(repo_path)

            commits = list(repo.traverse_commits())
            commit_chunks = vb_utils.split_list(commits, self.STORE_INTERVAL)

            for chunk in commit_chunks:
                args = [(repo_name, repo_path, commit) for commit in chunk]

                logging.warning('Pool starts computations')
                self._pool.map(self._get_commit_change_graphs, args)
                logging.warning('Pool stops')

        self._pool.close()
        self._pool.join()

    @staticmethod
    def _async_store_change_graphs(graphs):
        thread = threading.Thread(target=GitAnalyzer._store_change_graphs, args=(graphs,))
        thread.daemon = True
        thread.start()

    @staticmethod
    def _store_change_graphs(graphs):
        filename = uuid.uuid4().hex
        logging.warning(f'Storing graphs to {filename}')

        with open(f'storage/{filename}.pickle', 'w+b') as f:
            pickle.dump(graphs, f)

        logging.warning(f'Storing graphs to {filename} finished')

    @staticmethod
    def _get_commit_change_graphs(args):
        repo_name, repo_path, commit = args
        change_graphs = []

        commit_msg = commit.msg.replace('\n', '; ')
        GitAnalyzer._mp_log(f'Looking at commit #{commit.hash}, msg: "{commit_msg}"')

        if not commit.parents:
            return

        for mod in commit.modifications:
            if mod.change_type != ModificationType.MODIFY:
                continue

            if not mod.filename.endswith('.py'):
                continue

            old_src, new_src = mod.source_code_before, mod.source_code
            old_method_to_new = GitAnalyzer._get_methods_mapping(
                GitAnalyzer._extract_methods(old_src), GitAnalyzer._extract_methods(new_src))

            for old_method, new_method in old_method_to_new.items():
                old_method_src = old_method.get_source()
                new_method_src = new_method.get_source()

                if not all([old_method_src, new_method_src]) or old_method_src == new_method_src:
                    continue

                with tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as t1, \
                        tempfile.NamedTemporaryFile(mode='w+t', suffix='.py') as t2:

                    t1.writelines(old_method_src)
                    t1.seek(0)
                    t2.writelines(new_method_src)
                    t2.seek(0)

                    repo_info = RepoInfo(
                        repo_name, repo_path, commit.hash, commit.parents, old_method, new_method)

                    try:
                        cg = changegraph.build_from_files(
                            os.path.realpath(t1.name), os.path.realpath(t2.name), repo_info=repo_info)
                    except:
                        GitAnalyzer._mp_log(f'Unable to build a change graph for repo={repo_name}, commit={commit.hash}')
                        continue

                    change_graphs.append(cg)

                    if len(change_graphs) >= GitAnalyzer.STORE_INTERVAL:
                        GitAnalyzer._store_change_graphs(change_graphs)
                        change_graphs.clear()

        if len(change_graphs) >= GitAnalyzer.STORE_INTERVAL:
            GitAnalyzer._async_store_change_graphs(change_graphs)

    @staticmethod
    def _extract_methods(src):
        try:
            src_ast = ast.parse(src, mode='exec')
        except:
            GitAnalyzer._mp_log('Unable to compile src and extract methods')
            return []

        return ASTMethodExtractor(src).visit(src_ast)

    @staticmethod
    def _get_methods_mapping(old_methods, new_methods):
        old_method_to_new = {}
        for old_method in old_methods:
            for new_method in new_methods:
                if old_method.path == new_method.path:
                    old_method_to_new[old_method] = new_method
        return old_method_to_new

    @staticmethod
    def _mp_log(text):
        logging.warning(f'#{os.getpid()}: {text}')


class ASTMethodExtractor(ast.NodeVisitor):
    def __init__(self, src):
        self.src = src

    def visit_Module(self, node):
        methods = []
        for st in node.body:
            result = self.visit(st)
            if result:
                methods += result
        return methods

    def visit_ClassDef(self, node):
        methods = []
        for st in node.body:
            result = self.visit(st)
            if result:
                methods += result

        for method in methods:
            method.extend_path(node.name)

        return methods

    def visit_FunctionDef(self, node):
        return [Method(node.name, node, self.src)]


class Method:
    def __init__(self, name, ast, src):
        self.name = name
        self.ast = ast

        self.src = src.strip()
        self.path = name

    def extend_path(self, prefix, separator='.'):
        self.path = f'{prefix}{separator}{self.path}'

    # TODO:  last = lines[end_lineno].encode()[:end_col_offset].decode(), IndexError: list index out of range
    def get_source(self):
        try:
            return ast.get_source_segment(self.src, self.ast)
        except:
            return None


class RepoInfo:
    def __init__(self, repo_name, repo_path, commit_hash, commit_parents, old_method, new_method):
        self.repo_name = repo_name
        self.repo_path = repo_path

        self.commit_hash = commit_hash
        self.commit_parents = commit_parents

        self.old_method = old_method
        self.new_method = new_method
