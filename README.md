# Hybrid!

A journey from analyzer-backed SAI indexes to end-to-end hybrid search on Vectors.

Rough ToC:

1. Analyzer SAI: looking for the choices best suited to augment vector ANN search
2. Hybrid search with keyword provided explicitly: how to merge the two search conditions (vectors + keywords)
3. Automatic keyword determination from the query string, or: have a `search(query_text)` ready-to-use function.

Additionally, there may be further experiments, but the above is the main road.

Everything can be run with an Astra Vector DB (see `requirements.txt`).

Feel free to peruse the material, but probably following the 1-2-3 sequence is what works best.
