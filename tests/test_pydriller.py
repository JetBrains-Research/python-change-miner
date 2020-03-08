import pickle
import os

import objgraph
from pydriller import RepositoryMining

import settings


def main():
    repo_path = os.path.join(settings.get('git_repositories_dir'), 'trfl')
    repo = RepositoryMining(repo_path)

    commits = list(repo.traverse_commits())[:10]

    print(f'Starting with {len(objgraph.by_type("Commit"))}')
    for n, commit in enumerate(commits):
        pickle.dumps(commit)
        print(f'#{n+1} {len(objgraph.by_type("Commit"))}')
    print(f'Ending with {len(objgraph.by_type("Commit"))}')


if __name__ == '__main__':
    main()
