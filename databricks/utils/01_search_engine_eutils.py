# Databricks notebook source
# MAGIC %run ./00_query_translator 

# COMMAND ----------

# default_exp searchEngineUtils
from nbdev import *

# COMMAND ----------

# MAGIC %md # Search Engine Tools  
# MAGIC 
# MAGIC > A library of classes that provide query access to a number of online academic search services including (Pubmed, PMC, and European PMC). 

# COMMAND ----------

#export
"""
A package designed for interactions with the EUtils tools from the National Library of Medicine
"""
import requests
import json
import datetime
from enum import Enum
from urllib.request import urlopen
from urllib.parse import quote_plus
from urllib.error import URLError
from time import time,sleep
import re
from tqdm import tqdm
from bs4 import BeautifulSoup,Tag,Comment,NavigableString
import pandas as pd


PAGE_SIZE = 10000
TIME_THRESHOLD = 0.3333334

class NCBI_Database_Type(Enum):
  """
  Simple enumeration of the different NCBI databases supported by this tool
  """
  pubmed = 'pubmed'
  PMC = 'PMC'

class ESearchQuery:
    """
    Class to provide query interface for ESearch (i.e., query terms in elaborate ways, return a list of ids)
    Each instance of this class executes queries of a given type
    """

    def __init__(self, api_key=None, oa=False, db='pubmed'):
        """
        :param api_key: API Key for NCBI EUtil Services 
        :param oa: Is this query searching for open access papers? 
        :param db: The database being queried
        """
        self.api_key = api_key
        self.idPrefix = ''
        self.oa = oa
        self.db = db

    def execute_count_query(self, query):
        """
        Executes a query on the target database and returns a count of papers 
        """
        idPrefix = ''
        if self.oa:
            if self.db == NCBI_Database_Type.PMC:
                query = '"open access"[filter] AND (' + query + ')'
                idPrefix = 'PMC'
            elif self.db == NCBI_Database_Type.pubmed:
                query = '"loattrfree full text"[sb] AND (' + query + ')'
        if self.api_key: 
          esearch_stem = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?api_key='+self.api_key+'&db=' + self.db + '&term='
        else:
          esearch_stem = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db='+self.db + '&term='
        esearch_response = urlopen(esearch_stem + query)
        esearch_data = esearch_response.read().decode('utf-8')
        esearch_soup = BeautifulSoup(esearch_data, "lxml-xml")
        count_tag = esearch_soup.find('Count')
        if count_tag is None:
            raise Exception('No Data returned from "' + self.query + '"')
        return int(count_tag.string)
      
    def execute_query_on_website(self, q, pm_order='relevance'):
        """
        Executes a query on the Pubmed database and returns papers in order of relevance or date.
        This is important to determine accuracy of complex queries are based on the composition of the first page of results.  
        """
        query = 'https://pubmed.ncbi.nlm.nih.gov/?format=pmid&size=10&term='+re.sub('\s+','+',q)
        if pm_order == 'date':
            query += '&sort=date'
        response = urlopen(query)
        data = response.read().decode('utf-8')
        soup = BeautifulSoup(data, "lxml-xml")
        pmids = re.split('\s+', soup.find('body').text.strip())
        return pmids

    def execute_query(self, query):
        """
        Executes a query on the eutils service and returns data as a Pandas Dataframe
        """
        idPrefix = ''
        if self.oa:
            if self.db == NCBI_Database_Type.PMC:
                query = '"open access"[filter] AND (' + query + ')'
                idPrefix = 'PMC'
            elif self.db == NCBI_Database_Type.pubmed:
                query = '"loattrfree full text"[sb] AND (' + query + ')'
        
        if self.api_key: 
          esearch_stem = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?api_key='+self.api_key+'&db=' + self.db + '&term='
        else: 
          esearch_stem = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=' + self.db + '&term='
          
        #query = quote_plus(query)
        print(esearch_stem + query)
        esearch_response = urlopen(esearch_stem + query)
        esearch_data = esearch_response.read().decode('utf-8')
        esearch_soup = BeautifulSoup(esearch_data, "lxml-xml")
        count_tag = esearch_soup.find('Count')
        if count_tag is None:
            raise Exception('No Data returned from "' + query + '"')
        count = int(count_tag.string)

        latest_time = time()

        ids = []
        for i in tqdm(range(0,count,PAGE_SIZE)):
            full_query = esearch_stem + query + '&retstart=' + str(i)+ '&retmax=' + str(PAGE_SIZE)
            esearch_response = urlopen(full_query)
            esearch_data = esearch_response.read().decode('utf-8')
            esearch_soup = BeautifulSoup(esearch_data, "lxml-xml")
            for pmid_tag in esearch_soup.find_all('Id') :
                ids.append(self.idPrefix + pmid_tag.text)
            delta_time = time() - latest_time
            if delta_time < TIME_THRESHOLD :
                sleep(TIME_THRESHOLD - delta_time)

        return ids


# COMMAND ----------

show_doc(ESearchQuery.__init__)

# COMMAND ----------

show_doc(ESearchQuery.execute_count_query)

# COMMAND ----------

show_doc(ESearchQuery.execute_query_on_website)

# COMMAND ----------

show_doc(ESearchQuery.execute_query)

# COMMAND ----------

#export
class EFetchQuery:
    """
    Class to provide query interface for EFetch (i.e., query based on a list of ids)
    Each instance of this class executes queries of a given type
    """

    def __init__(self, api_key=None, db='pubmed'):
        """
        :param api_key: API Key for NCBI EUtil Services 
        :param oa: Is this query searching for open access papers? 
        :param db: The database being queried
        """
        self.api_key = api_key
        self.db = db

    def execute_efetch(self, id):
        """
        Executes a query for a single specific identifier
        """
        if self.api_key:
          efetch_stem = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?api_key='+self.api_key+'&db=pubmed&retmode=xml&id='
        else:
          efetch_stem = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id='
        efetch_response = urlopen(efetch_stem + str(id))
        return self._generate_rows_from_medline_records(efetch_response.read().decode('utf-8'))

    def generate_data_frame_from_id_list(self, id_list):
        """
        Executes a query for a list of ID values
        """
        if self.api_key:
          efetch_stem = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?api_key='+self.api_key+'&db=pubmed&retmode=xml&id='
        else:
          efetch_stem = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&retmode=xml&id='
        page_size = 100
        i = 0
        url = efetch_stem
        efetch_df = pd.DataFrame()
        for line in tqdm(id_list):
            try:
                l = re.split('\s+', str(line))
                pmid = l[0]
                i += 1
                if i >= page_size:
                    efetch_response = urlopen(url)
                    df = self._generate_rows_from_medline_records(efetch_response.read().decode('utf-8'))
                    efetch_df = efetch_df.append(df)
                    url = efetch_stem
                    i = 0

                if re.search('\d$', url):
                    url += ','
                url += pmid.strip()
            except URLError as e:
                sleep(10)
                print("URLError({0}): {1}".format(e.errno, e.strerror))
            except TypeError as e2:
                pause = 1

        if url != efetch_stem:
            efetch_response = urlopen(url)
            df = self._generate_rows_from_medline_records(efetch_response.read().decode('utf-8'))
            efetch_df = efetch_df.append(df)
        return efetch_df

    def generate_mesh_data_frame_from_id_list(self, id_list):
        """
        Executes a query for MeSH data from a list of ID values
        """
        url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
        if self.api_key:
          payload = 'api_key='+self.api_key+'&db=pubmed&retmode=xml&id='
        else:
          payload = 'db=pubmed&retmode=xml&id='
          
        headers = {'content-type': 'application/xml'}

        page_size = 10000
        i = 0
        efetch_df = pd.DataFrame()
        for line in tqdm(id_list):
            try:
                l = re.split('\s+', line)
                pmid = l[0]
                i += 1
                if i >= page_size:
                    print('   running query')
                    r = requests.post(url, data=payload)
                    efetch_data = r.content.decode('utf-8')
                    df = self._generate_mesh_rows_from_medline_records(efetch_data)
                    efetch_df = efetch_df.append(df)
                    payload = 'db=pubmed&retmode=xml&id='
                    i = 0

                if re.search('\d$', payload):
                    payload += ','
                payload += pmid.strip()
            except URLError as e:
                sleep(10)
                print("URLError({0}): {1}".format(e.errno, e.strerror))

        if payload[-1] != '=':
            r = requests.post(url, data=payload)
            efetch_data = r.content.decode('utf-8')
            df = self._generate_mesh_rows_from_medline_records(efetch_data)
            efetch_df = efetch_df.append(df)

        return efetch_df

    def _generate_mesh_rows_from_medline_records(self, record):

        soup2 = BeautifulSoup(record, "lxml-xml")

        rows = []
        cols = ['PMID','MESH']
        for citation_tag in tqdm(soup2.find_all('MedlineCitation')):

            pmid_tag = citation_tag.find('PMID')

            mesh_labels = []

            if pmid_tag is None:
                continue

            for meshTag in citation_tag.findAll('MeshHeading'):
                desc = meshTag.find('DescriptorName')
                qual_list = meshTag.findAll('QualifierName')
                if len(qual_list)>0:
                    mesh_labels.append('%s/%s'%(desc.text.replace('\n', ' '),'/'.join(q.text.replace('\n', ' ') for q in qual_list)))
                else:
                    mesh_labels.append(desc.text.replace('\n', ' '))
            mesh_data = ",".join(mesh_labels)

            rows.append((pmid_tag.text, mesh_data))

        df = pd.DataFrame(data=rows, columns=cols)
        return df

    def _generate_rows_from_medline_records(self, record):

        soup2 = BeautifulSoup(record, "lxml-xml")

        rows = []
        cols = ['PMID', 'YEAR', 'PUBLICATION_TYPE', 'TITLE', 'ABSTRACT','MESH','KEYWORDS']
        for citation_tag in soup2.find_all('MedlineCitation'):

            pmid_tag = citation_tag.find('PMID')
            title_tag = citation_tag.find('ArticleTitle')
            abstract_txt = ''
            for x in citation_tag.findAll('AbstractText'):
                if x.label is not None:
                    abstract_txt += ' ' + x.label + ': '
                abstract_txt += x.text

            mesh_labels = []
            for meshTag in citation_tag.findAll('MeshHeading'):
                desc = meshTag.find('DescriptorName')
                qual_list = meshTag.findAll('QualifierName')
                if len(qual_list)>0:
                    mesh_labels.append('%s/%s'%(desc.text.replace('\n', ' '),'/'.join(q.text.replace('\n', ' ') for q in qual_list)))
                else:
                    mesh_labels.append(desc.text.replace('\n', ' '))
            mesh_data = ",".join(mesh_labels)

            if pmid_tag is None or title_tag is None or abstract_txt == '':
                continue

            year_tag = citation_tag.find('PubDate').find('Year')

            year = ''
            if year_tag is not None:
                year = year_tag.text

            is_review = '|'.join([x.text for x in citation_tag.findAll('PublicationType')])

            keyword_data = '|'.join([meshTag.text.replace('\n', ' ') for meshTag in citation_tag.findAll('Keyword')])

            rows.append((pmid_tag.text, year, is_review, title_tag.text, abstract_txt, mesh_data, keyword_data))

        df = pd.DataFrame(data=rows, columns=cols)
        return df


# COMMAND ----------

show_doc(EFetchQuery.__init__)

# COMMAND ----------

show_doc(EFetchQuery.execute_efetch)

# COMMAND ----------

show_doc(EFetchQuery.generate_data_frame_from_id_list)

# COMMAND ----------

show_doc(EFetchQuery.generate_mesh_data_frame_from_id_list)

# COMMAND ----------

#export
class EuroPMCQuery():
    """
    A class that executes search queries on the European PMC API 
    """
    def __init__(self, oa=False, db='pubmed'):
        """
        Initialization of the class
        :param oa:
        """
        self.oa = oa

    def run_empc_query(self, q, page_size=1000):
        EMPC_API_URL = 'https://www.ebi.ac.uk/europepmc/webservices/rest/search?resultType=idlist&format=JSON&pageSize=' + str(
            page_size) + '&synonym=TRUE'
        url = EMPC_API_URL + '&query=' + q
        r = requests.get(url, timeout=10)
        data = json.loads(r.text)
        numFound = data['hitCount']
        print(q + ', ' + str(numFound) + ' European PMC PAPERS FOUND')
        pmids_from_q = set()
        otherIds_from_q = set()
        cursorMark = '*'
        for i in tqdm(range(0, numFound, page_size)):
            url = EMPC_API_URL + '&cursorMark=' + cursorMark + '&query=' + q
            r = requests.get(url)
            data = json.loads(r.text)
            # print(data.keys())
            if data.get('nextCursorMark'):
                cursorMark = data['nextCursorMark']
            for d in data['resultList']['result']:
                if d.get('pmid'):
                    pmids_from_q.add(str(d['pmid']))
                else:
                    otherIds_from_q.add(str(d['id']))
            # pp.pprint(data)
            # break
        return (numFound, list(pmids_from_q))


# COMMAND ----------

show_doc(EuroPMCQuery.__init__)

# COMMAND ----------

show_doc(EuroPMCQuery.run_empc_query)

# COMMAND ----------

query = [{'ID':0, 'query': '("Neurodegeneration" | "Neurodegenerative disease" | "Alzheimers Disease" | "Parkinsons Disease") & "Machine Learning"'}]
df = pd.DataFrame(query)
qt = QueryTranslator(df, 'query')
print(qt.generate_queries(QueryType.pubmed))

# COMMAND ----------

# tests
# uncomment if needed.
import urllib.parse 
from time import time, sleep

esq = ESearchQuery()
pcd_search = urllib.parse.quote("Primary Ciliary Dyskinesia")
print(esq.execute_count_query(pcd_search))
sleep(3) # Sleep for 3 seconds
esq.execute_query(pcd_search)

efq = EFetchQuery()
sleep(3) # Sleep for 3 seconds
efq.execute_efetch(35777446)

# COMMAND ----------

# Tests for European PMC
epmcq = EuroPMCQuery()
id_list, q_list = qt.generate_queries(QueryType.epmc)
epmcq.run_empc_query(q_list[0])

