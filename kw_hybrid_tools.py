from operator import itemgetter

HYBRID_ANN_QUERY_TEMPLATE = """
SELECT snippet, similarity_cosine(embedding, %s) as similarity
FROM {keyspace}.snippets
  {where_clause}
  ORDER BY embedding ANN OF %s
  LIMIT %s ;
"""


def create_where_parts(keywords, placeholder='%s', logical_joiner='AND'):
    where_clause_pieces = [
        f"snippet : {placeholder}"
        for _ in sorted(set(keywords))
    ]
    where_clause_args = sorted(set(keywords))
    if where_clause_pieces:
        return (' WHERE ' + (f' {logical_joiner} ').join(where_clause_pieces), where_clause_args)
    else:
        return ('', list())


# Draft implementations, don't take these too seriously for real texts

PUNKT = set('!,.?;\'"-+=/[]{}()\n')

def keyword_similarity(snippet, keywords=[], min=0.0, max=1.0):
    # if no keywords, we always return the max - to avoid breaking simpler flows
    if not keywords:
        return max
    else:
        _snp = ''.join([c for c in snippet if c not in PUNKT]).lower()
        toks = {tk for tk in _snp.split(' ') if tk}
        kw_set = set(keywords)
        num_kw = len(kw_set)
        num_hits = len(toks & kw_set)
        return min + (max - min) * num_hits / num_kw


def sum_score_merger(ann_sim, kw_sim, rho=0.5):
    return (1-rho)*ann_sim + rho*kw_sim


def combine_ann_with_kw_similarity(ann_results, keywords, kw_similarity_function=keyword_similarity, score_merger_function=sum_score_merger):
    # kw_similarity_function must accept a (text, kw_list) signature - possibly through partialing
    return sorted(
        (
            (
                snp,
                (score_merger_function(ann_sim, kw_similarity_function(snp, keywords))),
            )
            for snp, ann_sim in ann_results
        ),
        key=itemgetter(1),
        reverse=True,
    )


def hybrid_ann_anykeyword(session, keyspace, get_embeddings, query, keywords=[], top_k=3):
    q_vector = get_embeddings([query])[0]
    #
    wc, wc_vals = create_where_parts(keywords, logical_joiner='OR')
    #
    hybrid_query = HYBRID_ANN_QUERY_TEMPLATE.format(keyspace=keyspace, where_clause=wc)
    hq_values = tuple([q_vector] + wc_vals + [q_vector, top_k])
    return [
        (row.snippet, row.similarity)
        for row in session.execute(hybrid_query, hq_values)
    ]


def hybrid_search_with_kw(session, keyspace, get_embeddings, query, keywords=[], top_k=3, kw_similarity_function=keyword_similarity,
                          score_merger_function=sum_score_merger, prefetch_factor=5):
    prefetch_k = prefetch_factor * top_k if keywords else top_k
    # Warning: wasteful implementation, that's not the point :)
    return combine_ann_with_kw_similarity(
        hybrid_ann_anykeyword(session, keyspace, get_embeddings, query, keywords, prefetch_k),
        keywords,
        kw_similarity_function=kw_similarity_function,
        score_merger_function=score_merger_function,
    )[:top_k]


def show(results):
    for ri, (sn, si) in enumerate(results):
        print(f"    [{ri+1}] {si:.5f} \"{sn}\"")
