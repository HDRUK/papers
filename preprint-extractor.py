#!/usr/bin/env python
# usage: preprint-extractor.py
__author__ = "Susheel Varma"
__copyright__ = "Copyright (c) 2019-2020 Susheel Varma All Rights Reserved."
__email__ = "susheel.varma@hdruk.ac.uk"
__license__ = "MIT"

import sys
import time
import csv
import json
import urllib
from datetime import datetime
from operator import itemgetter
import psutil
import requests
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import ray

# Based on https://api.biorxiv.org/covid19/help
BIORXIV_COVID_API_URL = "https://api.biorxiv.org/covid19/{}"
HDRUK_MEMBERS_CSV = "C:\Users\user\Documents\HDR-FILE\contacts.csv"    #/home/runner/secrets/contacts.csv
# HDRUK_MEMBERS_CSV = "data/contacts.csv"

num_cpus = psutil.cpu_count(logical=False)
ray.init(num_cpus=num_cpus)

def request_url(URL):
    """HTTP GET request and load into json"""
    r = requests.get(URL)
    if r.status_code != requests.codes.ok:
        r.raise_for_status()
    return json.loads(r.text)

def read_json(filename):
  with open(filename, 'r') as file:
    return json.load(file)

def write_json(data, filename, indent=2):
  with open(filename, 'w') as jsonfile:
    json.dump(data, jsonfile, indent=indent)

def write_csv(data, header, outputFilename):
  with open(outputFilename, 'w') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=header)
    writer.writeheader()
    writer.writerows(data)

def read_csv(filename):
  header = []
  data = []
  with open(filename, mode='r', encoding='utf-8-sig', newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    header = reader.fieldnames
    for row in reader:
      data.append(row)
  return data, header

def retrieve_preprints(BASE_URL, data=None, page=0):
    DATA = data or []
    URL = BASE_URL.format(page)
    print("Retrieving preprints from", URL)
    d = request_url(URL)
    cursor = int(d['messages'][0]['cursor'])
    count = int(d['messages'][0]['count'])
    total = int(d['messages'][0]['total'])
    page = (cursor+count)+1
    print("cursor:{} count:{} total:{}".format(cursor, count, total))
    DATA.extend(d['collection'])

    if page < total:
        time.sleep(1)
        retrieve_preprints(BIORXIV_COVID_API_URL, DATA, page)
    return DATA

def fuzzy_match_lists(value_list, match_list):
    max_match_value = 0
    for value in value_list:
        matches = process.extract(value, match_list, scorer=fuzz.token_set_ratio)
        match_value = max(matches, key = itemgetter(1))[1]
        if int(match_value) > int(max_match_value): max_match_value = match_value
    return max_match_value

def match_lists(value_list, match_list):
    for v in value_list:
        if v.lower() in (match.lower() for match in match_list):
            return 100
    return 0

@ray.remote
def filter_preprint(i, p, num_preprints, authors, affiliations):
    fuzzy_row = None
    exact_row = None
    doi = p.get('rel_doi', "")
    if p.get('rel_authors', None) is not None:
        preprint_authors = [a['author_name'] for a in p['rel_authors']]
        for a in preprint_authors:
            split_a = a.split(' ')
            if len(split_a) > 2:
                a = split_a[0] + " " + split_a[-1]
        preprint_affiliations = [a['author_inst'] for a in p['rel_authors']]
        doi_max_author_match = 0
        doi_max_affiliation_match = 0
        print("{}/{} Processing authors and affiliations for doi:{}".format(i+1, num_preprints, doi))
        # Fuzzy match author
        doi_max_author_match = fuzzy_match_lists(preprint_authors, authors)
        # Fuzzy match affilaition
        doi_max_affiliation_match = fuzzy_match_lists(preprint_affiliations, affiliations)
        print("Author Fuzzy Match: {} | Affiliation Fuzzy Match: {}".format(doi_max_author_match, doi_max_affiliation_match))
        
        if doi_max_author_match >= 95 and doi_max_affiliation_match >= 95:
            fuzzy_row = {
                'site': p.get('rel_site', ""),
                'doi': doi,
                'date': p.get('rel_date',""),
                'link': p.get('rel_link', ""),
                'title': p.get('rel_title', ""),
                'authors': "; ".join(preprint_authors),
                'affiliations': "; ".join(preprint_affiliations),
                'abstract': p.get('rel_abs', ""),
                'category': p.get('category', ""),
                'match_type': "fuzzy",
                'author_similarity': doi_max_author_match,
                'affiliation_similarity': doi_max_affiliation_match
            }
            print(fuzzy_row)
        # Exact match author
        doi_max_author_match = match_lists(preprint_authors, authors)
        # Exact match affilaition
        doi_max_affiliation_match = match_lists(preprint_affiliations, affiliations)
        print("Author Exact Match: {} | Affiliation Exact Match: {}".format(doi_max_author_match, doi_max_affiliation_match))
        
        if doi_max_author_match >= 90 and doi_max_affiliation_match >= 90:
            exact_row = {
                'site': p.get('rel_site', ""),
                'doi': doi,
                'date': p.get('rel_date',""),
                'link': p.get('rel_link', ""),
                'title': p.get('rel_title', ""),
                'authors': "; ".join(preprint_authors),
                'affiliations': "; ".join(preprint_affiliations),
                'abstract': p.get('rel_abs', ""),
                'category': p.get('category', ""),
                'match_type': "exact",
                'author_similarity': doi_max_author_match,
                'affiliation_similarity': doi_max_affiliation_match
            }
            print(exact_row)
    return (fuzzy_row, exact_row)

def filter_preprints(preprints):
    found = 0
    authors = []
    affiliations = []
    members, header = read_csv(HDRUK_MEMBERS_CSV)
    for a in members:
        authors.append(a['Full Name'])
        affiliations.append(a['Affiliation'])
    affiliations = list(set(affiliations))
    affiliations.extend(["HDRUK", "HDR UK", "HDR-UK", "HEALTH DATA RESEARCH UK", "HEALTH DATA RESEARCH UK LTD"])
    ray_authors_id = ray.put(authors)
    ray_affiliations_id = ray.put(affiliations)

    num_preprints = len(preprints)
    ray_num_preprints_id = ray.put(num_preprints)

    futures = []
    for i, p in enumerate(preprints):
        futures.append(filter_preprint.remote(i, p, ray_num_preprints_id, ray_authors_id, ray_affiliations_id))
    # Get match results
    results = ray.get(futures)
    fuzzy_data = [r[0] for r in results if r[0] is not None]
    exact_data = [r[1] for r in results if r[1] is not None]
    return fuzzy_data, exact_data

def generate_summary(preprints):
    data = []
    headers = []
    summaries = {}
    for p in preprints:
        date_obj = datetime.strptime(p['date'], "%Y-%m-%d")
        month_year = datetime.strftime(date_obj, "%b-%y")
        if month_year not in summaries.keys(): summaries[month_year] = {"Total": 0}
        summaries[month_year]['Total'] += 1
        if p['category'] not in summaries[month_year].keys(): summaries[month_year][p['category']] = 0
        summaries[month_year][p['category']] += 1
    for month, summary in summaries.items():
        row = { 'month': month}
        row.update(summary)
        headers.extend(row.keys())
        data.append(row)
    headers = list(set(headers))
    return data, headers


def main():
    # read old preprint extract
    old_data = read_json('data/covid/raw-preprints.json')

    # retrieve new preprint extract
    data = retrieve_preprints(BIORXIV_COVID_API_URL)
    write_json(data, 'data/covid/raw-preprints.json')

    # check if length of new extract is more than old extract. fail if not.
    if len(old_data) >= len(data):
        print("Error: New extract ({}) smaller than previous extract ({})".format(len(data), len(old_data)))
        sys.exit(1)

    # data = read_json('data/covid/raw-preprints.json')
    
    # filter preprints for HDR UK authors and affilaitions
    fuzzy_data, exact_data = filter_preprints(data)
    headers = ['site', 'doi', 'date', 'link', 'title', 'authors', 'affiliations', 'abstract', 'category', 'match_type', 'author_similarity', 'affiliation_similarity']
    write_json(fuzzy_data, 'data/covid/preprints.json')
    write_csv(fuzzy_data, headers, "data/covid/preprints.csv")

    write_json(exact_data, 'data/covid/preprints.exact.json')
    write_csv(exact_data, headers, "data/covid/preprints.exact.csv")

    # generate preprint summary
    summary, headers = generate_summary(fuzzy_data)
    write_csv(summary, headers, "data/covid/preprints-summary.csv")
    


if __name__ == "__main__":
    main()
