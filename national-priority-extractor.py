#!/usr/bin/env python
# usage: preprint-extractor.py
__author__ = "Susheel Varma"
__copyright__ = "Copyright (c) 2019-2020 Susheel Varma All Rights Reserved."
__email__ = "susheel.varma@hdruk.ac.uk"
__license__ = "MIT"

import csv
import json
import urllib
import requests
from pprint import pprint

EPMC_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?resultType=core&pageSize=1000&format=json&"

NATIONAL_PRIORITIES_CSV = "data/national-priorities.csv"

def export_json(data, filename, indent=2):
  with open(filename, 'w') as jsonfile:
    json.dump(data, jsonfile, indent=indent)

def export_csv(data, header, outputFilename):
  with open(outputFilename, 'w') as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=header)
    writer.writeheader()
    writer.writerows(data)

def request_url(URL :str):
  """HTTP GET request and load into json"""
  r = requests.get(URL)
  if r.status_code != requests.codes.ok:
    r.raise_for_status()
  return json.loads(r.text)

def read_csv(filename: str):
  header = []
  data = []
  with open(filename, mode='r', encoding='utf-8-sig', newline='') as csvfile:
    reader = csv.DictReader(csvfile)
    header = reader.fieldnames
    for row in reader:
      data.append(row)
  return header, data

def match_title(title, data):
    split_title = title.split()
    # Match title on first 7 words
    title = " ".join(split_title[0:7])
    for d in data['resultList']['result']:
        if 'title' in d.keys():
            if d.get('title').startswith(title):
                return d
    return None

def match_id(id, data):
  for d in data['resultList']['result']:
    if d.get('id') == id:
      return d
  return None

def extract_paper_from_title(title :str, data :dict):
  URL = EPMC_BASE_URL + "query=" + urllib.parse.quote_plus(title)
  print(URL)
  d = request_url(URL)
  paper = match_title(title, d)
  return paper

def extract_paper_from_id(id: str, data: dict):
  URL = EPMC_BASE_URL + "query=" + urllib.parse.quote_plus(id)
  print(URL)
  d = request_url(URL)
  paper = match_id(id, d)
  return paper


def format_data(data):
  HEADER = ['id', 'doi', 'originalTitle', 'title', 'authorString', 'authorAffiliations', 'journalTitle', 'pubYear', 'isOpenAccess', 'keywords', 'nationalPriorities', 'healthCategories', 'abstract', 'urls']
  DATA = []
  for d in data:
    print(d['id'])

    # Extracting Author affiliations
    authorAffiliations = []
    if 'authorList' in d.keys():
      for author in d['authorList']['author']:
        if 'authorAffiliationsList' in author.keys():
          if 'authorAffiliation' in author['authorAffiliationsList'].keys():
            if None not in author['authorAffiliationsList']['authorAffiliation']:
              affiliation = "; ".join(author['authorAffiliationsList']['authorAffiliation'])
              authorAffiliations.append(affiliation)
    # Extracting URLS
    URLS = []
    if d.get('fullTextUrlList', None) is not None:
      for url in d.get('fullTextUrlList')['fullTextUrl']:
        URLS.append("{}:{}".format(url['documentStyle'], url['url']))
    
    # Extracting Keywords
    keywords = ""
    if 'keywordList' in d.keys():
      keywords = keywords + "; ".join(d['keywordList']['keyword'])
    if d.get('journalInfo', None) is None:
      journalTitle = "No Journal Info"
    else:
      journalTitle = d.get('journalInfo')['journal']['title']
    row = {
      'id': d.get('id', ''),
      'doi': "https://doi.org/" + d.get('doi',''),
      'originalTitle': d.get('original title', ''),
      'title': d.get('title', ''),
      'authorString': d.get('authorString', ''),
      'authorAffiliations': "; ".join(authorAffiliations),
      'journalTitle': journalTitle,
      'pubYear': d.get('pubYear', ''),
      'isOpenAccess': d.get('isOpenAccess', ''),
      'keywords': keywords,
      'nationalPriorities': d.get('national priority', ''),
      'healthCategories': d.get('health category', ''),
      'abstract': d.get('abstractText', '')
    }
    if len(URLS):
      row['urls'] = "; ".join(URLS)
    else:
      row['urls'] = ""
    DATA.append(row)
  return HEADER, DATA

def main():
    NP_PAPERS = []
    NP_PAPERS_NOT_FOUND = []
    header, national_priorities = read_csv(NATIONAL_PRIORITIES_CSV)
    header.append('original title')
    total = len(national_priorities)
    for i, np in enumerate(national_priorities):
        print("Extracting %s/%s" % (i+1,total))
        if np.get('id', "") != "":
          paper = extract_paper_from_id(np['id'], np)
        else:
          paper = extract_paper_from_title(np['title'], np)
        if paper is not None:
            paper['original title'] = np['title']
            paper['national priority'] = np['national priority']
            paper['health category'] = np['health category']
            NP_PAPERS.append(paper)
        else:
          np['original title'] = np['title']
          NP_PAPERS.append(np)
    
    header, data = format_data(NP_PAPERS)
    export_csv(data, header, 'data/national-priorities.csv')

if __name__ == "__main__":
    main()