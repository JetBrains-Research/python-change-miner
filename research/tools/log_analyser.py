import re
import os
import time
import matplotlib.pyplot as plt
import datetime
from collections import OrderedDict

import logging
import settings

LOGS_DIR = settings.get('research_logs_dir')


def search_file(pattern, from_time=None, excluded_files=None):
    if excluded_files is None:
        excluded_files = []

    results = []
    regexp = re.compile(pattern)
    time_regexp = re.compile('\\[[0-9]{2}.[0-9]{2}.[0-9]{4} [0-9]{2}:[0-9]{2}:[0-9]{2}\\]')

    for filename in os.listdir(LOGS_DIR):
        if not filename.endswith('.log') or filename in excluded_files:
            continue

        logging.warning(f'Looking at file {filename}')
        file_path = os.path.join(LOGS_DIR, filename)

        last_result = None
        with open(file_path, 'r+') as f:
            lines = [line for line in f]

        for lo, line in enumerate(lines):
            logging.warning(f'Line [{lo + 1}/{len(lines)}]')

            if not line.startswith('['):
                if last_result:
                    last_result['log'] += line
                continue
            else:
                last_result = None

            if from_time is not None:
                m = re.match(time_regexp, line)
                dtm_str = m.group(0).lstrip('[').rstrip(']')

                dtm = datetime.datetime.strptime(dtm_str, '%d.%m.%Y %H:%M:%S')
                if dtm < from_time:
                    continue

            result = {
                'matches': re.search(regexp, line),
                'log': line
            }
            if result['matches']:
                results.append(result)
                last_result = result

    logging.warning(f'Found {len(results)} matches')
    return results


def plt_items_for_seconds():
    pattern = 'Gumtree... OK (?P<time>[0-9]+)ms'
    from_time = datetime.datetime(day=16, month=3, year=2020, hour=16, minute=0)
    results = search_file(pattern, from_time=from_time, excluded_files=['miner.log'])

    cnt_timer_arr = []
    for result in results:
        cnt = 1  # int(result['matches'].group('cnt'))
        tm = int(result['matches'].group('time'))

        cnt_timer_arr.append((cnt, tm))

    cnt_timer_arr = sorted(cnt_timer_arr, key=lambda tpl: tpl[0])

    fig = plt.figure()
    axes = fig.gca()
    for cnt, tm in cnt_timer_arr:
        axes.scatter(cnt, int(tm), marker='+')

    plt.yticks(fontsize=12)
    plt.xticks(fontsize=12, rotation=0)
    plt.xlabel('Items cnt')
    plt.ylabel('Time in seconds')

    fig.show()

    output_path = os.path.join(LOGS_DIR, 'output')
    os.makedirs(output_path, exist_ok=True)

    time_in_ms = int(time.time())
    output_path = os.path.join(output_path, str(time_in_ms))
    fig.savefig(output_path)


def print_frequent_items():
    LAST_LINES_LIMIT = 5
    SHOW_LOGS_LIMIT = 10

    pattern = 'Unable to build a change graph for repo='
    results = search_file(pattern, excluded_files=['test.log', 'miner0.log'])

    id_to_result = {}
    for result in results:
        lines = result['log'].split('\n')
        result_id = '; '.join(lines[-LAST_LINES_LIMIT:])

        arr = id_to_result.setdefault(result_id, [])
        arr.append(result)

    od = OrderedDict(sorted(id_to_result.items(), key=lambda el: len(el[1]), reverse=True))
    cnt = 1
    for k, v in od.items():
        if cnt > SHOW_LOGS_LIMIT:
            break
        cnt += 1

        logging.warning(f'Frequency: {len(v)}')
        logging.warning(f'Stacktrace: \n{v[0]["log"]}')


if __name__ == '__main__':
    plt_items_for_seconds()
    # print_frequent_items()
