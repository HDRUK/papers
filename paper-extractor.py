#!/usr/bin/env python
# usage: paper-extractor.py
__author__ = "Susheel Varma"
__copyright__ = "Copyright (c) 2019-2020 Susheel Varma All Rights Reserved."
__email__ = "susheel.varma@hdruk.ac.uk"
__license__ = "Apache 2"

import csv
import json
import urllib
import requests
from pprint import pprint

EPMC_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search?resultType=core&pageSize=1000&format=json&"
PMCID_LOOKUP_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={}&format=json&tool=my_tool&email=my_email@example.com"

HDRUK_PAPERS_QUERY = "((ACK_FUND:\"HDRUK\" OR ACK_FUND:\"HDR UK\" OR ACK_FUND:\"HDR-UK\" OR ACK_FUND:\"Health Data Research UK\" OR ACK_FUND: \"MC_PC_20029\" OR ACK_FUND: \"MC_PC_20058\") OR (AFF:\"HDRUK\" OR AFF:\"HDR UK\" OR AFF:\"HDR-UK\" OR AFF:\"Health Data Research UK\")) AND NOT (SRC:PPR)"
COVID_PAPERS_QUERY = "(\"2019-nCoV\" OR \"2019nCoV\" OR \"COVID-19\" OR \"SARS-CoV-2\" OR \"COVID19\" OR \"COVID\" OR \"SARS-nCoV\" OR (\"wuhan\" AND \"coronavirus\") OR \"Coronavirus\" OR \"Corona virus\" OR \"corona-virus\" OR \"corona viruses\" OR \"coronaviruses\" OR \"SARS-CoV\" OR \"Orthocoronavirinae\" OR \"MERS-CoV\" OR \"Severe Acute Respiratory Syndrome\" OR \"Middle East Respiratory Syndrome\" OR (\"SARS\" AND \"virus\") OR \"soluble ACE2\" OR (\"ACE2\" AND \"virus\") OR (\"ARDS\" AND \"virus\") or (\"angiotensin-converting enzyme 2\" AND \"virus\")) AND ((ACK_FUND:\"HDRUK\" OR ACK_FUND:\"HDR UK\" OR ACK_FUND:\"HDR-UK\" OR ACK_FUND:\"Health Data Research UK\" OR ACK_FUND: \"MC_PC_20029\" OR ACK_FUND: \"MC_PC_20058\") OR (AFF:\"HDRUK\" OR AFF:\"HDR UK\" OR AFF:\"HDR-UK\" OR AFF:\"Health Data Research UK\")) AND NOT (SRC:PPR)"
COVID_PREPRINTS_QUERY = "(\"2019-nCoV\" OR \"2019nCoV\" OR \"COVID-19\" OR \"SARS-CoV-2\" OR \"COVID19\" OR \"COVID\" OR \"SARS-nCoV\" OR (\"wuhan\" AND \"coronavirus\") OR \"Coronavirus\" OR \"Corona virus\" OR \"corona-virus\" OR \"corona viruses\" OR \"coronaviruses\" OR \"SARS-CoV\" OR \"Orthocoronavirinae\" OR \"MERS-CoV\" OR \"Severe Acute Respiratory Syndrome\" OR \"Middle East Respiratory Syndrome\" OR (\"SARS\" AND \"virus\") OR \"soluble ACE2\" OR (\"ACE2\" AND \"virus\") OR (\"ARDS\" AND \"virus\") or (\"angiotensin-converting enzyme 2\" AND \"virus\")) AND ((ACK_FUND:\"HDRUK\" OR ACK_FUND:\"HDR UK\" OR ACK_FUND:\"HDR-UK\" OR ACK_FUND:\"Health Data Research UK\" OR ACK_FUND: \"MC_PC_20029\" OR ACK_FUND: \"MC_PC_20058\") OR (AFF:\"HDRUK\" OR AFF:\"HDR UK\" OR AFF:\"HDR-UK\" OR AFF:\"Health Data Research UK\")) AND (SRC:PPR)"

# HDR UK Custom tags
NATIONAL_PRIORITIES_CSV = "data/national-priorities.csv"
LAY_SUMMARIES_CSV = "data/lay-summaries.csv"

def request_url(URL):
  """HTTP GET request and load into json"""
  r = requests.get(URL)
  if r.status_code != requests.codes.ok:
    r.raise_for_status()
  return json.loads(r.text)


def retrieve_papers(query="", data=None, cursorMark="*"):
  if data is None:
    DATA = []
  else:
    DATA = data
  query = urllib.parse.quote_plus(query)
  URL = EPMC_BASE_URL + "&".join(["query=%s" % query, "cursorMark=%s" % cursorMark])
  print("Retrieving papers from", URL)
  d = request_url(URL)
  numResults = d['hitCount']
  DATA.extend(d['resultList']['result'])
  if numResults > 1000:
    retrieve_papers(query, DATA, cursorMark=d['nextCursorMark'])
  return DATA

def get_dois_from_pmcids(data):
  pmcids = ",".join([ p['id'] for p in data if p['doi'] == 'https://doi.org/' and p['id'].startswith('PMC')])
  ret = request_url(PMCID_LOOKUP_URL.format(pmcids))
  for r in ret['records']:
    for d in data:
      if d['id'] == r['pmcid']:
        d['doi'] = "https://doi.org/" + r['doi']
  return data

def export_json(data, filename, indent=2):
  with open(filename, 'w') as jsonfile:
    json.dump(data, jsonfile, indent=indent)

def export_csv(data, header, outputFilename):
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

NATIONAL_PRIORITIES, NP_HEADER = read_csv(NATIONAL_PRIORITIES_CSV)

def get_national_priorities(d):
  for np in NATIONAL_PRIORITIES:
    if d.get('id') == np['id']:
      return {
        'nationalPriorities': np['nationalPriorities'],
        'healthCategories': np['healthCategories']
      }
  return {
        'nationalPriorities': "",
        'healthCategories': ""
      }

LAY_SUMMARIES, LS_HEADER = read_csv(LAY_SUMMARIES_CSV)

def get_lay_summary(d):
  doi = "https://doi.org/" + d.get('doi','')
  for ls in LAY_SUMMARIES:
    if ls['doi'] == doi:
      return ls['lay summary']
  return ""

def format_data(data):
  HEADER = ['id', 'doi', 'title', 'authorString', 'authorAffiliations', 'journalTitle', 'pubYear', 'date', 'isOpenAccess', 'keywords', 'nationalPriorities', 'healthCategories', 'abstract', 'laySummary', 'urls']
  DATA = []
  for d in data:
    print(d['id'])
    # Get National Priorities & Health Categories
    np = get_national_priorities(d)
    # Get lay Summary
    lay_summary = get_lay_summary(d)

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
      'title': d.get('title'),
      'authorString': d.get('authorString'),
      'authorAffiliations': "; ".join(authorAffiliations),
      'journalTitle': journalTitle,
      'pubYear': d.get('pubYear'),
      'date': d.get('firstPublicationDate', None),
      'isOpenAccess': d.get('isOpenAccess'),
      'keywords': keywords,
      'nationalPriorities': np['nationalPriorities'],
      'healthCategories': np['healthCategories'],
      'abstract': d.get('abstractText', ''),
      'laySummary': lay_summary
    }
    if len(URLS):
      row['urls'] = "; ".join(URLS)
    else:
      row['urls'] = ""
    DATA.append(row)
  return DATA, HEADER

def merge(key, *lists):
  import itertools
  from collections import defaultdict
  result = defaultdict(dict)
  for dictionary in itertools.chain.from_iterable(lists):
    result[dictionary[str(key)]].update(dictionary)
  return list(result.values())


def main():
  # retrieve papers with author affiliation or funding acknowledgement to HDR-UK
  papers = retrieve_papers(query=HDRUK_PAPERS_QUERY, data=[])
  data, header = format_data(papers)
  # data = get_dois_from_pmcids(data)
  export_csv(data, header, 'data/papers.csv')
  export_json(data, 'data/papers.json')
  
  # retrieve COVID-19 papers with author affiliation or funding acknowledgement to HDR-UK
  covid_papers = retrieve_papers(query=COVID_PAPERS_QUERY, data=[])
  data, header = format_data(covid_papers)
  export_csv(data, header, 'data/covid/papers.csv')

  # retrieve COVID-19 preprints with author affiliation or funding acknowledgement to HDR-UK
  covid_preprints = retrieve_papers(query=COVID_PREPRINTS_QUERY, data=[])
  data, header = format_data(covid_preprints)
  export_csv(data, header, 'data/covid/ack-preprints.csv')


if __name__ == "__main__":
    main()
