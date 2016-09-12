import datetime


class ElasticsearchStorage(object):
    def __init__(self, elasticsearch_hosts, elasticsearch_index, elasticsearch_doctype, logger,
                 default_machine_id=None):
        try:
            import elasticsearch
        except ImportError as exc:
            raise ImportError(exc.args, "Please install elasticsearch or pytest-benchmark[elasticsearch]")
        self._elasticsearch_hosts = elasticsearch_hosts
        self._elasticsearch_index = elasticsearch_index
        self._elasticsearch_doctype = elasticsearch_doctype
        self._elasticsearch = elasticsearch.Elasticsearch(self._elasticsearch_hosts)
        self.default_machine_id = default_machine_id
        self.logger = logger
        self._cache = {}
        self._create_index()

    def __str__(self):
        return str(self._elasticsearch_hosts)

    @property
    def location(self):
        return str(self._elasticsearch_hosts)

    def query(self, project):
        """
        Returns sorted records names (ids) that corresponds with project.
        """
        return [commit_and_time for commit_and_time, _ in self.load(project)]

    def load(self, project, id_prefix=None):
        """
        Yield key and content of records that corresponds with project name.
        """
        r = self._search(project, id_prefix)
        groupped_data = self._group_by_commit_and_time(r["hits"]["hits"])
        result = [(key, value) for key, value in groupped_data.items()]
        result.sort(key=lambda x: datetime.datetime.strptime(x[1]["datetime"], "%Y-%m-%dT%H:%M:%S.%f"))
        for key, data in result:
            yield key, data

    def _search(self, project, id_prefix=None):
        body = {
            "size": 1000,
            "sort": [
                {
                    "datetime": {
                        "order": "desc"
                    }
                }
            ],
            "query": {
                "bool": {
                    "filter": {
                        "term": {
                            "commit_info.project": project
                        }
                    }
                }
            }
        }
        if id_prefix:
            body["query"]["bool"]["must"] = {
                "prefix": {
                    "_id": id_prefix
                }
            }

        return self._elasticsearch.search(index=self._elasticsearch_index,
                                          doc_type=self._elasticsearch_doctype,
                                          body=body)

    @staticmethod
    def _benchmark_from_es_record(source_es_record):
        result = {}
        for benchmark_key in ("group", "stats", "options", "param", "name", "params", "fullname"):
            result[benchmark_key] = source_es_record[benchmark_key]
        return result

    @staticmethod
    def _run_info_from_es_record(source_es_record):
        result = {}
        for run_key in ("machine_info", "commit_info", "datetime", "version"):
            result[run_key] = source_es_record[run_key]
        return result

    def _group_by_commit_and_time(self, hits):
        result = {}
        for hit in hits:
            source_hit = hit["_source"]
            key = "%s_%s" % (source_hit["commit_info"]["id"], source_hit["datetime"])
            benchmark = self._benchmark_from_es_record(source_hit)
            if key in result:
                result[key]["benchmarks"].append(benchmark)
            else:
                run_info = self._run_info_from_es_record(source_hit)
                run_info["benchmarks"] = [benchmark]
                result[key] = run_info
        return result

    def load_benchmarks(self, project):
        """
        Yield benchmarks that corresponds with project. Put path and
        source (uncommon part of path) to benchmark dict.
        """
        r = self._search(project)
        for hit in r["hits"]["hits"]:
            yield self._benchmark_from_es_record(hit["_source"])

    def save(self, document, document_id):
        self._elasticsearch.index(
            index=self._elasticsearch_index,
            doc_type=self._elasticsearch_doctype,
            body=document,
            id=document_id,
        )

    def _create_index(self):
        mapping = {
            "mappings": {
                "benchmark": {
                    "properties": {
                        "commit_info": {
                            "properties": {
                                "dirty": {
                                    "type": "boolean"
                                },
                                "id": {
                                    "type": "string",
                                    "index": "not_analyzed"

                                },
                                "project": {
                                    "type": "string",
                                    "index": "not_analyzed"
                                }
                            }
                        },
                        "datetime": {
                            "type": "date",
                            "format": "strict_date_optional_time||epoch_millis"
                        },
                        "name": {
                            "type": "string",
                            "index": "not_analyzed"
                        },
                        "fullname": {
                            "type": "string",
                            "index": "not_analyzed"
                        },
                        "version": {
                            "type": "string",
                            "index": "not_analyzed"
                        },
                        "machine_info": {
                            "properties": {
                                "machine": {
                                    "type": "string",
                                    "index": "not_analyzed"
                                },
                                "node": {
                                    "type": "string",
                                    "index": "not_analyzed"
                                },
                                "processor": {
                                    "type": "string",
                                    "index": "not_analyzed"
                                },
                                "python_build": {
                                    "type": "string",
                                    "index": "not_analyzed"
                                },
                                "python_compiler": {
                                    "type": "string",
                                    "index": "not_analyzed"
                                },
                                "python_implementation": {
                                    "type": "string",
                                    "index": "not_analyzed"
                                },
                                "python_implementation_version": {
                                    "type": "string",
                                    "index": "not_analyzed"
                                },
                                "python_version": {
                                    "type": "string",
                                    "index": "not_analyzed"
                                },
                                "release": {
                                    "type": "string",
                                    "index": "not_analyzed"
                                },
                                "system": {
                                    "type": "string",
                                    "index": "not_analyzed"
                                }
                            }
                        },
                        "options": {
                            "properties": {
                                "disable_gc": {
                                    "type": "boolean"
                                },
                                "max_time": {
                                    "type": "double"
                                },
                                "min_rounds": {
                                    "type": "long"
                                },
                                "min_time": {
                                    "type": "double"
                                },
                                "timer": {
                                    "type": "string"
                                },
                                "warmup": {
                                    "type": "boolean"
                                }
                            }
                        },
                        "stats": {
                            "properties": {
                                "hd15iqr": {
                                    "type": "double"
                                },
                                "iqr": {
                                    "type": "double"
                                },
                                "iqr_outliers": {
                                    "type": "long"
                                },
                                "iterations": {
                                    "type": "long"
                                },
                                "ld15iqr": {
                                    "type": "double"
                                },
                                "max": {
                                    "type": "double"
                                },
                                "mean": {
                                    "type": "double"
                                },
                                "median": {
                                    "type": "double"
                                },
                                "min": {
                                    "type": "double"
                                },
                                "outliers": {
                                    "type": "string"
                                },
                                "q1": {
                                    "type": "double"
                                },
                                "q3": {
                                    "type": "double"
                                },
                                "rounds": {
                                    "type": "long"
                                },
                                "stddev": {
                                    "type": "double"
                                },
                                "stddev_outliers": {
                                    "type": "long"
                                }
                            }
                        },
                    }
                }
            }
        }
        self._elasticsearch.indices.create(index=self._elasticsearch_index, ignore=400, body=mapping)
