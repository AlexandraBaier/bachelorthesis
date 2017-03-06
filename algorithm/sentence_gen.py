import abc
import logging
import random
import sqlite3
from typing import Iterable, Iterator, List

import pathos.multiprocessing as mp


class Wikidata2Sequence(object, metaclass=abc.ABCMeta):

    @abc.abstractclassmethod
    def get_sequences(self)->Iterable[List[str]]:
        pass


class TripleSentences(Wikidata2Sequence):

    def __init__(self, items: Iterator[dict]):
        self.__items = items  # type: Iterator[dict]

    def get_sequences(self)->Iterable[List[str]]:
        def __get_sentences():
            for item in self.__items:
                item_id = item['id']
                for pid in item['claims'].keys():
                    stmt_group = item['claims'][pid]
                    for stmt in stmt_group:
                        if stmt['mainsnak']['snaktype'] == 'value' and stmt['mainsnak'].get('datatype'):
                            if stmt['mainsnak']['datatype'] == 'wikibase-item':
                                value = 'Q' + str(stmt['mainsnak']['datavalue']['value']['numeric-id'])
                            elif stmt['mainsnak']['datatype'] == 'wikibase-property':
                                value = 'P' + str(stmt['mainsnak']['datavalue']['value']['numeric-id'])
                            else:
                                value = stmt['mainsnak']['datatype']
                            yield [item_id, pid, value]
        return __get_sentences()


class GraphWalkSentences(Wikidata2Sequence):
    """
    GraphWalk has exponential runtime.
    """
    def __init__(self, vertices: List[str], depth: int, max_walks_per_v: int, edge_store_path: str, workers: int=4):
        self.__vertices = vertices  # type: List[str]
        self.__depth = depth  # type: int
        self.__max_walks = max_walks_per_v  # type: int
        self.__edge_store_path = edge_store_path
        self.__workers = workers

    def get_sequences(self)->Iterable[List[str]]:
        logging.log(level=logging.INFO, msg='Graph walk sequences with depth={}, max walks={}, workers={}'.format(
            self.__depth, self.__max_walks, self.__workers
        ))

        def __get_sequences():
            with mp.Pool(processes=self.__workers) as p:
                for walks in p.imap_unordered(self.__get_walks, self.__vertices):
                    for w in walks:
                        yield w

        return __get_sequences()

    def __get_walks(self, vertice: str):
        logging.log(level=logging.INFO, msg='start computing walks from {}'.format(vertice))

        random.seed()

        walks = [[vertice if idx == 0 else '' for idx, _ in enumerate(range(2*self.__depth+1))]
                 for _ in range(self.__max_walks)]
        queue = [(vertice, 0)]

        out_edge_cache = dict()

        with sqlite3.connect(self.__edge_store_path) as conn:
            while len(queue) > 0:
                current_vertice, current_depth = queue.pop(0)
                logging.log(level=logging.DEBUG, msg='depth={}, queue={}'.format(current_depth, len(queue)))
                # current vertice is already at max depth => skip this vertice
                if current_depth >= self.__depth:
                    continue
                if not out_edge_cache.get(current_vertice, None):
                    out_edges = self.__get_out_edges(current_vertice, conn)
                    out_edge_cache[current_vertice] = out_edges
                else:
                    logging.log(level=logging.DEBUG, msg='cache hit for {}'.format(current_vertice))
                    out_edges = out_edge_cache[current_vertice]
                m = len(out_edges)
                # current vertice has no out-edges => skip this vertice
                if m == 0:
                    logging.log(level=logging.INFO, msg='{} has no out-edges'.format(current_vertice))
                    continue
                for walk_id in range(self.__max_walks):
                    # current walk doesn't end with current vertice or is already computed => skip this walk
                    if walks[walk_id][2*current_depth] != current_vertice or walks[walk_id][2*current_depth+1] != '':
                        continue
                    r = random.randint(0, m-1)
                    chosen_edge = out_edges[r]
                    walks[walk_id][2*current_depth+1] = chosen_edge[1]  # add edge weight to walk
                    walks[walk_id][2*current_depth+2] = chosen_edge[2]  # add target to walk
                    if (chosen_edge[2], current_depth+1) not in queue:
                        queue.append((chosen_edge[2], current_depth+1))

        # strip empty strings of walk, remove walks with length 1
        for walk_id in range(self.__max_walks):
            walks[walk_id] = list(filter(lambda s: s != '', walks[walk_id]))
        walks = list(filter(lambda walk: len(walk) > 1, walks))
        logging.log(level=logging.INFO, msg='{} paths discovered from {}'.format(len(walks), vertice))
        return walks

    @staticmethod
    def __get_out_edges(v: str, conn)->List[List[str]]:
        c = conn.cursor()
        node = int(v[1:])
        c.execute('SELECT * FROM edges WHERE s=?', [node])
        results = c.fetchall()
        return list(map(lambda e: ['Q'+str(e[0]), 'P'+str(e[1]), 'Q'+str(e[2])], results))


class SentenceIterator(Iterator[List[str]]):

    def __init__(self, file_path: str):
        self.__path = file_path  # type: str

    def __iter__(self):
        with open(self.__path) as f:
            for s in map(lambda l: l.strip().split(), f):
                yield s if s[2][0] in ['Q', 'P'] else s[0:2]
