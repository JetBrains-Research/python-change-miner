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
_QUERY_STRING = settings.get('research_repo_query_string')
_TOKEN = settings.get('research_github_token', required=False)


def main():
    logging.warning('Starting')

    page_num = 1
    visited_repo_cnt = 1
    stars = _MIN_STARS
    max_repo_cnt = _REPO_CNT

    while True:
        if visited_repo_cnt > max_repo_cnt or stars < _MIN_STARS:
            break

        headers = {'Authorization': f'token {_TOKEN}'} if _TOKEN else None
        r = requests.get(f'{_GITHUB_BASE_URL}/search/repositories?'
                         f'q={_QUERY_STRING}&page={page_num}&per_page=100',
                         headers=headers)
        data = r.json()
        items = data.get('items')
        max_repo_cnt = min(max_repo_cnt, data.get('total_count'))

        if not items:
            logging.warning(f'No items, response_data={data}')
            break

        for item in items:
            repo_name = re.sub('/', '---', item['full_name'])
            stars = item['stargazers_count']
            if stars < _MIN_STARS:
                logging.warning(f'Stopped, no enough stars in repo={repo_name}, stars={stars} < {_MIN_STARS}')
                break

            args = ['git', 'clone', item['clone_url'], os.path.join(_REPO_DIR, repo_name)]
            p = subprocess.Popen(args, stdout=subprocess.PIPE)
            p.communicate()

            logging.warning(f'Visited repo={repo_name}, stars={stars} [{visited_repo_cnt}/{_REPO_CNT}]')

            visited_repo_cnt += 1
            if visited_repo_cnt > max_repo_cnt:
                break

        page_num += 1

    logging.warning('Done')


if __name__ == '__main__':
    main()
