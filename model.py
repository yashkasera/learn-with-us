import spacy
import os
import pytextrank
import networkx as nx
import math
import operator
import nltk
import pickle
from string import punctuation

import language_tool_python

root = os.path.dirname(os.path.abspath(__file__))
download_dir = os.path.join(root, 'my_nltk_dir')
nltk.data.path.append(download_dir)
from nltk.tokenize import sent_tokenize, word_tokenize

nlp = spacy.load('en_core_web_sm')
nlp.add_pipe("textrank")

STOP_WORDS_FILE_NAME = 'stop_words'
infile = open(STOP_WORDS_FILE_NAME, "rb")
stop_words = pickle.load(infile)
infile.close()


tool = language_tool_python.LanguageToolPublicAPI('en-US')


def increment_edge(graph, node0, node1):
    if graph.has_edge(node0, node1):
        graph[node0][node1]["weight"] += 1.0

    else:
        graph.add_edge(node0, node1, weight=1.0)


POS_KEPT = ["NOUN", "ADJ", "VERB"]


def link_sentence(doc, sent, lemma_graph, seen_lemma):
    visited_tokens = []
    visited_nodes = []

    for i in range(sent.start, sent.end):

        token = doc[i]

        if token.pos_ in POS_KEPT:
            key = (token.lemma_, token.pos_)

            if key not in seen_lemma:
                seen_lemma[key] = {token.i}
            else:
                seen_lemma[key].add(token.i)

            node_id = list(seen_lemma.keys()).index(key)

            if not node_id in lemma_graph:
                lemma_graph.add_node(node_id)

            for prev_token in range(len(visited_tokens) - 1, -1, -1):

                if (token.i - visited_tokens[prev_token]) <= 3:
                    increment_edge(lemma_graph, node_id, visited_nodes[prev_token])
                else:
                    break

            visited_tokens.append(token.i)
            visited_nodes.append(node_id)


# This function will collect all the words and give its rank
def collect_phrases(chunk, phrases, counts):
    chunk_len = chunk.end - chunk.start
    sq_sum_rank = 0.0
    non_lemma = 0
    compound_key = set([])

    for i in range(chunk.start, chunk.end):
        token = doc[i]
        key = (token.lemma_, token.pos_)

        if key in seen_lemma:
            node_id = list(seen_lemma.keys()).index(key)
            rank = ranks[node_id]
            sq_sum_rank += rank
            # depending on its frequency and importance its given a rank
            compound_key.add(key)

        else:
            non_lemma += 1

    # although the noun chunking is greedy, we discount the ranks using a
    # point estimate based on the number of non-lemma tokens within a phrase
    non_lemma_discount = chunk_len / (chunk_len + (2.0 * non_lemma) + 1.0)

    # use root mean square (RMS) to normalize the contributions of all the tokens
    phrase_rank = math.sqrt(sq_sum_rank / (chunk_len + non_lemma))
    phrase_rank *= non_lemma_discount

    # remove spurious punctuation
    phrase = chunk.text.lower().replace("'", "")

    # create a unique key for the the phrase based on its lemma components
    compound_key = tuple(sorted(list(compound_key)))

    if not compound_key in phrases:
        phrases[compound_key] = set([(phrase, phrase_rank)])
        counts[compound_key] = 1

    else:
        phrases[compound_key].add((phrase, phrase_rank))
        counts[compound_key] += 1


def get_keywords(text):
    global doc, seen_lemma, ranks
    sentence_words = nltk.word_tokenize(text)
    str2 = ''
    for word in sentence_words:
        if word not in punctuation and word not in stop_words:
            str2 = str2 + ' ' + word
    text = str2

    # Here we will add the text required on which NLP will take place
    # We add a pipeline at the start of every run

    # We reinitialise the model everytime
    doc = nlp(text)

    lemma_graph = nx.Graph()
    seen_lemma = {}

    for sent in doc.sents:
        link_sentence(doc, sent, lemma_graph, seen_lemma)
        # break
        # only test one sentence

    labels = {}
    keys = list(seen_lemma.keys())

    # Here we iterate through each sentence to construct their graph
    for i in range(len(seen_lemma)):
        labels[i] = keys[i][0].lower()

    # This variable will store the rank of each node of the graph
    ranks = nx.pagerank(lemma_graph)

    phrases = {}
    counts = {}

    for chunk in doc.noun_chunks:
        # here we collect all the phrases along with their frequency
        collect_phrases(chunk, phrases, counts)

    for ent in doc.ents:
        collect_phrases(ent, phrases, counts)

    min_phrases = {}

    for compound_key, rank_tuples in phrases.items():
        l = list(rank_tuples)
        l.sort(key=operator.itemgetter(1), reverse=True)
        phrase, rank = l[0]
        count = counts[compound_key]
        min_phrases[phrase] = (rank, count)

    list1 = []
    for node_id, rank in sorted(ranks.items(), key=lambda x: x[1], reverse=True):
        list1.append(labels[node_id])
    #    print(labels[node_id], rank)

    # Returns the list of the ranked words

    return list1


def check_grammar(text):
    matches = tool.check(text)
    errors = []
    if matches:
        for sentence in matches:
            # errors.append(sentence.__dict__)
            errors.append({"error": sentence.__dict__["message"]})
    return errors if len(errors) > 0 else None


if __name__ == "__main__":
    text = "He is an boy"
    # print(check_grammar(text))
