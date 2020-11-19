import requests
import os
import logging
import subprocess
import re

import settings

_GITHUB_BASE_URL = 'https://api.github.com'
_REPO_DIR = settings.get('research_repo_dir', os.getcwd())
_REPO_CNT = settings.get('research_repo_count', 10)

_MIN_STARS = settings.get('research_min_stars', 15)
_STARS_STEP = settings.get('research_stars_step', 500)
_MAX_STARS = settings.get('research_max_stars', 10 ** 9)
_STAR_BASED_SEARCH = settings.get('research_star_based_search', True)
_REPOS_PER_STAR = settings.get('research_repos_per_star', 3)

_QUERY_LANGUAGE = settings.get('research_query_language', 'python')
_TOKEN = settings.get('research_github_token', required=False)


def main():
    logging.warning('Starting')

    page_num = 1
    visited_repo_cnt = 0
    stars = _MAX_STARS
    max_repo_cnt = _REPO_CNT

    while True:
        if visited_repo_cnt >= max_repo_cnt or stars < _MIN_STARS:
            break

        q = ''
        if _STAR_BASED_SEARCH and stars < 10 ** 9:
            q = f'+stars:{stars}..{stars + _STARS_STEP}'
        q = f'language:{_QUERY_LANGUAGE}{q}&sort=stars&order=desc'

        headers = {'Authorization': f'token {_TOKEN}'} if _TOKEN else None
        r = requests.get(f'{_GITHUB_BASE_URL}/search/repositories?q={q}&page=1&per_page=100', headers=headers)

        data = r.json()
        items = data.get('items')

        if not items:
            logging.warning(f'No items, response_data={data}')
            stars -= _STARS_STEP
            continue

        curr_stars = -1
        stars_to_cnt = {}
        for item in items:
            if visited_repo_cnt >= max_repo_cnt:
                break

            visited_repo_cnt += 1
            curr_stars = item['stargazers_count']
            repo_name = re.sub('/', '---', item['full_name'])

            logging.warning(f'Looking at repo={repo_name}, stars={curr_stars} [{visited_repo_cnt}/{max_repo_cnt}]')

            val = stars_to_cnt.setdefault(curr_stars, 0)
            stars_to_cnt[stars] = val + 1
            if stars_to_cnt.get(stars) > _REPOS_PER_STAR:
                continue

            args = ['git', 'clone', item['clone_url'], os.path.join(_REPO_DIR, repo_name)]
            p = subprocess.Popen(args, stdout=subprocess.PIPE)
            p.communicate()

        stars = curr_stars - _STARS_STEP
        page_num += 1

    logging.warning('Done')


if __name__ == '__main__':
    main()
