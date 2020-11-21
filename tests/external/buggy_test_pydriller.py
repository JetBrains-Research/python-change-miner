import pickle
import os

import objgraph
from pydriller import RepositoryMining

import settings


def test_commits_pickling():
    repo_path = os.path.join(settings.get('git_repositories_dir'), 'trfl')
    repo = RepositoryMining(repo_path)

    commits = list(repo.traverse_commits())[:10]

    cnt_before = len(objgraph.by_type("Commit"))
    print(f'Starting with {cnt_before}')
    for n, commit in enumerate(commits):
        pickle.dumps(commit)
        print(f'#{n + 1} {len(objgraph.by_type("Commit"))}')

    cnt_after = len(objgraph.by_type("Commit"))
    print(f'Ending with {cnt_after}')

    assert cnt_before == cnt_after  # Track issue on https://github.com/ishepard/pydriller/issues/102


if __name__ == '__main__':
    test_commits_pickling()
