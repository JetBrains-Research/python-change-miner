import json
import os


def extract_relevant_commits(path_to_patterns: str):
    hashes, repos = set(), set()
    for root, dirs, files in os.walk(path_to_patterns):
        for file in files:
            if file.startswith('sample-details') and file.endswith('.json'):
                with open(os.path.join(root, file), 'r') as json_file:
                    details = json.load(json_file)
                    hashes.add(details['commit']['hash'])
                    repos.add(details['repo']['url'])
    for hash in hashes:
        print(hash)
    return repos, hashes


def main():
    repos, hashes = extract_relevant_commits('/home/oleg/prog/data/plugin/output_final_best/')
    res = {
        'repos': list(repos),
        'hashes': list(hashes)
    }
    with open('11_patterns_details.json', 'w') as json_file:
        json.dump(res, json_file)


if __name__ == '__main__':
    main()
