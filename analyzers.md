# Analyzers, index explorations (aka Part 1/3)

_A mini example to highlight basics of analyzers (+vectors)._

Inspired by:Madhavan's hands-on quickstart (which covers vectors+analyzers as well)

The following has been run in _production_.

#### Misc notes:

- the index analyzer (i.e. "don't touch the query") is now available in prod as well
- the vector column does not come back automatically anymore in ANN searches (yeah)
- can query `system_views.indexes` to check for index status
- still some trouble when a SAI-based query fails badly, which affects subsequently other things with that keyspace.

## Schema

Table and vector index

```
CREATE TABLE mydata (
    pk INT PRIMARY KEY,
    name TEXT,
    body TEXT,
    vals VECTOR<FLOAT, 2>
);
CREATE CUSTOM INDEX idx_vals ON mydata (vals) USING 'StorageAttachedIndex';
```

## Data

```
INSERT INTO mydata (pk, name, body, vals) VALUES (1, 'Ann', 'A lizard said bad things to the snakes', [0.1, 0.1]);
INSERT INTO mydata (pk, name, body, vals) VALUES (2, 'Bea', 'Please wear protective gear before operating the machine', [0.2, -0.3]);
INSERT INTO mydata (pk, name, body, vals) VALUES (3, 'Cal', 'My name is Slim Shady', [0.0, 0.9]);
INSERT INTO mydata (pk, name, body, vals) VALUES (4, 'Bea', 'I repeat: wear your helmet!', [0.3, -0.2]);
```

#### ANN sanity check

```
SELECT * FROM mydata ORDER BY vals ANN OF [0.3, 0.1] LIMIT 2;
```

returns rows 1, 4.

## "standard" SAI

```
CREATE CUSTOM INDEX idx_name ON mydata (name) USING 'StorageAttachedIndex';
```

```
SELECT * FROM mydata WHERE name='Bea';
```

returns 2, 4

## Mixing indexes

ANN and the `name` index:

```
SELECT * FROM mydata WHERE name='Bea' ORDER BY vals ANN OF [0.3, 0.1] LIMIT 2;
```

returns 4, 2 (order matters).

Multiple conditions on an index

```
SELECT * FROM mydata WHERE name='Bea' OR name='Ann' ORDER BY vals ANN OF [0.3, 0.1] LIMIT 5;
```

returns 1, 4, 2 (order matters).



## Enter analyzers

### Standard analyzer SAI

```
CREATE CUSTOM INDEX idx_body ON mydata (body) USING 'StorageAttachedIndex' WITH OPTIONS = { 'index_analyzer': 'standard'};
```

Sanity check (with combinations). Note "body" works in case-insensitive manner.

```
SELECT * FROM mydata WHERE body: 'machine';
-- returns 2

SELECT * FROM mydata WHERE body: 'Wear';
-- returns 2, 4

SELECT * FROM mydata WHERE body: 'Wear' AND name='Bea';
-- returns 2, 4

SELECT * FROM mydata WHERE body: 'WEAR' AND name='Bea' ORDER BY vals ANN OF [0.1, 0.2] LIMIT 3;
-- returns 4, 2 (order matters)
```

### Stemming analyzer

```
DROP INDEX idx_body;
CREATE CUSTOM INDEX idx_body ON mydata (body) USING 'StorageAttachedIndex'
  WITH OPTIONS = {'index_analyzer': '{ "tokenizer" :   {"name" : "standard"}, "filters" : [{"name" : "porterstem"}] }'};
```

Note this is NOT case-insensitive. So the above queries:

```
SELECT * FROM mydata WHERE body: 'machine';
-- returns 2
SELECT * FROM mydata WHERE body: 'Machine';
-- returns NOTHING

SELECT * FROM mydata WHERE body: 'wear';
-- returns 2, 4
SELECT * FROM mydata WHERE body: 'Wear';
-- returns NOTHING

SELECT * FROM mydata WHERE body: 'wear' AND name='Bea';
-- returns 2, 4
SELECT * FROM mydata WHERE body: 'Wear' AND name='Bea';
-- returns NOTHING

SELECT * FROM mydata WHERE body: 'wear' AND name='Bea' ORDER BY vals ANN OF [0.1, 0.2] LIMIT 3;
-- returns 4, 2 (order matters)
SELECT * FROM mydata WHERE body: 'WEAR' AND name='Bea' ORDER BY vals ANN OF [0.1, 0.2] LIMIT 3;
-- returns NOTHING
```

### Stemming and case-insensitive

(let's reformat the options for readability, even though they are in a long string)

```
DROP INDEX idx_body;
CREATE CUSTOM INDEX idx_body ON mydata (body) USING 'StorageAttachedIndex'
  WITH OPTIONS = {
    'index_analyzer': '{
      "tokenizer": {
        "name": "standard"
      },
      "filters": [
        {
          "name": "lowercase"
        },
        {
          "name":
          "porterstem"
        }
      ]
    }'
  };
```

Re-run the queries above, all the "NOTHING" ones now return the same as the corresponding right-cased queries.

#### EdgeNGram

For "text starts with '...'" queries.

```
DROP INDEX idx_body;
CREATE CUSTOM INDEX idx_body ON mydata (body) USING 'StorageAttachedIndex'
  WITH OPTIONS = {
    'index_analyzer': '{
      "tokenizer": {
        "name": "edgeNGram",
        "args": {
          "minGramSize": 1,
          "maxGramSize": 3
        }
      },
      "filters": [
        {
          "name": "lowercase"
        },
        {
          "name":
          "porterstem"
        }
      ]
    }'
  };
```

Note we also have `lowercase`. If you take that out, the wrong-cased would give no results (left as an exercise).

```
SELECT * FROM mydata WHERE body: 'Plea';
SELECT * FROM mydata WHERE body: 'Please';
SELECT * FROM mydata WHERE body: 'Please, I rep';
SELECT * FROM mydata WHERE body: 'please';
SELECT * FROM mydata WHERE body: 'PLEAS';
-- returns 2

SELECT * FROM mydata WHERE body: 'pl' AND name='Bea';
SELECT * FROM mydata WHERE body: 'PL' AND name='Bea';
-- returns 2

SELECT * FROM mydata WHERE body: 'pl' AND name='Bea' ORDER BY vals ANN OF [0.1, 0.2] LIMIT 3;
-- returns 2 (order would matter, were it more than 1 result :)
```

#### NGram

Thi works a bit as substring ("LIKE").

But: use with care - risk of combinatorial explosion for large texts/queries.

```
DROP INDEX various_clients_lastname_idx_analyzer;

DROP INDEX various_clients_firstname_idex_analyzer;
```

Create a "substring" index for (limited) "like" kind of things:

```
DROP INDEX idx_body;
CREATE CUSTOM INDEX idx_body ON mydata (body) USING 'StorageAttachedIndex'
  WITH OPTIONS = {
    'index_analyzer': '{
      "tokenizer": {
        "name": "ngram",
        "args": {
          "minGramSize": 2,
          "maxGramSize": 3
        }
      },
      "filters": [
        {
          "name": "lowercase"
        }
      ]
    }'
  };
```

```
SELECT * FROM mydata WHERE body: 'wear';
SELECT * FROM mydata WHERE body: 'WEAR';
-- SURPRISE: returns 2, 4 BUT ALSO 1 (possibly unexpected)

SELECT * FROM mydata WHERE body: 'ar pra';
SELECT * FROM mydata WHERE body: 'AR PRa';
-- SURPRISE: returns 2, despite the one-char mismatch (possibly unexpected)

SELECT * FROM mydata WHERE body: 'ar pro';
SELECT * FROM mydata WHERE body: 'AR PRO';
-- returns 2

SELECT * FROM mydata WHERE body: 'wear' AND name='Bea';
SELECT * FROM mydata WHERE body: 'WEAR' AND name='Bea';
-- returns 2, 4

SELECT * FROM mydata WHERE body: 'wear' AND name='Bea' ORDER BY vals ANN OF [0.1, 0.2] LIMIT 3;
SELECT * FROM mydata WHERE body: 'WEAR' AND name='Bea' ORDER BY vals ANN OF [0.1, 0.2] LIMIT 3;
-- returns 4, 2 (order matters)
```

> IMPORTANT: NGrams may find "too many" matches, considering the query string is also analyzed and then "a lot of stuff matches with a lot of stuff". Result: spurious matches (see the first two groups of queries above).

### Stemming and NGram

> TODO: explore the excess of matches from combining `porterstem` and `ngram`.

It would likely result in even more spurious/unexpected matches than above,
as the texts are first stemmed and then smashed into atoms.

Probably a discouraged combination in most realistic use cases.

### Keyword query analyzer (aka "untouched query")

NEW: one can specify an identity function for processing the _query_ only, to mitigate the above too-many-matches problem
(through the `'query_analyzer': 'keyword'` option).

But this requires some care, as we'll soon see:

#### NGram + untouched query

```
DROP INDEX idx_body;
CREATE CUSTOM INDEX idx_body ON mydata (body) USING 'StorageAttachedIndex'
  WITH OPTIONS = {
    'index_analyzer': '{
      "tokenizer": {
        "name": "ngram",
        "args": {
          "minGramSize": 2,
          "maxGramSize": 3
        }
      },
      "filters": [
        {
          "name": "lowercase"
        }
      ]
    }',
    'query_analyzer': 'keyword'
  };
```

Careful here: the rows are NGrammed, but the query isn't. So you'll have matches only if producing the very ngrams:

```
SELECT * FROM mydata WHERE body: 'wear';
-- returns NOTHING: this is a 4-gram, too long!
SELECT * FROM mydata WHERE body: 'wea';
-- returns 2, 4 (3-gram, matches as is)
SELECT * FROM mydata WHERE body: 'we';
-- returns 2, 4 (2-gram, matches as is)
SELECT * FROM mydata WHERE body: 'w';
-- returns NOTHING: this is a 1-gram, too short!

SELECT * FROM mydata WHERE body: 'WEa';
-- returns NOTHING, rows are lowercased and query is used as is
SELECT * FROM mydata WHERE body: 'WE';
-- returns NOTHING, rows are lowercased and query is used as is
```

Also with the usual SAI combination:

```
SELECT * FROM mydata WHERE body: 'we' AND name='Bea' ORDER BY vals ANN OF [0.1, 0.2] LIMIT 3;
-- returns 4, 2 (order matters)
```

#### Stemming + untouched query

This is more likely a good use case (also less prone to combinatorial explosion performance risks).

```
DROP INDEX idx_body;
CREATE CUSTOM INDEX idx_body ON mydata (body) USING 'StorageAttachedIndex'
  WITH OPTIONS = {
    'index_analyzer': '{
      "tokenizer": {
        "name": "standard"
      },
      "filters": [
        {
          "name": "lowercase"
        },
        {
          "name": "porterstem"
        }
      ]
    }',
    'query_analyzer': 'keyword'
  };
```

Of course this is not "substring" or anything like that. It's (stemmed) tokens. And for a purpose.

Remember query is as is, you'll have to provide them lowercased.

### Now stop here for the time being.

The following is being debugged right now. Don't run these queries,
as they might put your DB in a bad state (overall!).

> `SELECT * FROM mydata WHERE name='Bea' AND body: 'wear' OR body: 'snake';` counts as "nested" as it has AND + OR operators.


This **would** be to test (postponed):

```
SELECT * FROM mydata WHERE body: 'wear';

SELECT * FROM mydata WHERE body: 'wear' OR body: 'snake';
-- Note 'snake', singular form

SELECT * FROM mydata WHERE (body: 'wear' OR body: 'snake') AND name='Bea';

SELECT * FROM mydata WHERE body: 'wear' OR body: 'snake' AND name='Bea';
-- Note the parenthese (...)

SELECT * FROM mydata WHERE body: 'wear' OR body: 'snake' ORDER BY vals ANN OF [0.1, 0.2] LIMIT 3;

SELECT * FROM mydata WHERE body: 'wear' OR body: 'snake' AND name='Bea' ORDER BY vals ANN OF [0.1, 0.2] LIMIT 3;
```
