from elasticsearch import Elasticsearch

class SearchService:
    def __init__(self, es):
        self.es = es

    def search(self, query):
        results = self.es.search(index="award_travel", body={"query": {"match": {"description": query}}})
        return results["hits"]["hits"]

    def filter(self, query):
        results = self.es.search(index="award_travel", body={"query": {"bool": {"must": [{"match": {"description": query}}]}}})
        return results["hits"]["hits"]
