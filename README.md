# CSV join audit

A small Apify Actor implementation for checking whether two CSV inputs satisfy
an exact-key many-to-one join and how many observations lack a lookup match.
It is intended as a tool a data-analysis agent can call before trusting a join.

**Verification status:** ten local functional tests and four actual local Apify SDK
processes pass on Python 3.13.9, Apify 4.0.2 and pandas 2.3.3. The local SDK runs
verify all four verdicts, identical dataset/key-value reports, and preserved input.
On September 14, 2026, Apify Console built source commit
`cd38092e790252fe785cb8aad4e994b38a62378f` as build `0.0.2` and completed four
synthetic cloud cases with the expected verdicts. Cloud logs report Python
3.13.15 and Apify SDK 4.0.2; pandas 2.3.3 is pinned in the built requirements.
The input/output schemas passed the actual platform build. A real agent call
through the Apify MCP server remains unverified. This README is product
documentation, not the proposed commissioned article. No client engagement,
publication, or earnings are claimed.

## Input

Supply exactly three fields: `observationsCsv`, `lookupCsv`, and `key`.
Both CSV strings need a header. Key text is preserved exactly: `001`, `1`, `NA`
and ` 001` are different values. Blank or whitespace-only keys block the join.
The tool does not trim, infer missing markers, choose a duplicate, or repair data.

Limits per CSV: 200,000 UTF-8 bytes, 500 data rows, 50 columns, and 512 UTF-8 bytes
per key value. The key column name is limited to 100 characters. Quoted commas
and embedded newlines are supported. Row positions in diagnostics are one-based
logical data records, excluding the header; they are not physical line numbers.

## Read the verdict, not just the run status

| Verdict | Meaning | Next action |
| --- | --- | --- |
| `invalid_input` | Arguments or CSV structure are invalid. | Correct arguments; no join was performed. |
| `blocked` | A key is blank or a lookup key is duplicated. | Resolve the source data; never auto-deduplicate. |
| `needs_review` | Lookup cardinality passes, but observations are empty or some are unmatched. | Resolve coverage or explicitly decide how it affects the analysis. |
| `checks_passed` | These exact-key cardinality and coverage checks pass. | Check measurement semantics before computing an aggregate. |

Every result is saved as one dataset row and as key-value record `OUTPUT`.
An Actor can finish successfully while returning `blocked` or `invalid_input`.
That separation is intentional: a completed diagnosis is not approval to proceed.
Examples are capped at ten per issue type; counts cover the entire bounded input.
Reports include key values but do not echo other CSV columns.

The implementation does not validate values, units, timestamps, sampling,
aggregate correctness or composite keys. It does not fetch URLs, mutate a source,
write to external business systems, or call a paid model. Running in Apify still
uses platform resources and stores input/output there; verify usage limits before
a cloud run and use only data authorized for that destination.

## Run locally

Use Python 3.11 or later; the development environment uses Python 3.13.9.

```sh
python -m pip install -r requirements.txt
python -m unittest -v test_audit
```

For a local SDK run, place input JSON at
`storage/key_value_stores/default/INPUT.json` and run `python main.py`.
Keep verification storage outside the deliverable source. Set
`APIFY_LOCAL_STORAGE_DIR` to the desired local verification directory. No API token
is needed for a local SDK run. Local execution does not verify cloud or MCP behavior.
In SDK 4.0.2 the local `OUTPUT` record is stored without a `.json` filename
extension; its metadata declares JSON. Consumers should read through the storage
API instead of assuming a local filename extension.

## Cloud verification

The `.actor` directory contains the Actor definition and input/output schemas.
Import the public repository as an Actor Git source and build it. The original
cloud build exposed a missing `type: "string"` on each output URL entry; the
fixed schema is included here. The Actor runs with limited permissions.

The four observed Console runs used 256 MB memory, a 60-second timeout, a
US$0.05 maximum per run, and restart-on-error off. Each run exited with code 0
and one dataset result. The verdict, rather than process success, determines
whether analysis can proceed. Report fields below were checked in the actual
Console output and logs; full dataset/key-value equivalence was tested locally.

| Synthetic case | Report verdict | Observed evidence |
| --- | --- | --- |
| Four observations; lookup contains two `001` rows | `blocked` | One duplicate lookup key; `canJoinManyToOne` false; no join counts |
| Remove the duplicate but omit lookup key `999` | `needs_review` | Three matched observations; one unmatched, logical data row 4, key `999` |
| Add a unique lookup entry for `999` | `checks_passed` | Four matched observations; zero unmatched |
| Supply a two-column header followed by a three-field row | `invalid_input` | Wrong-number-of-fields reason; no join performed |

All examples use invented data. The deployed Actor and cloud run records are
private; this repository is public. The Docker base tag is `python:3.13-slim`,
so a future rebuild may use a newer Python patch version. The observed cloud
run durations were approximately 2-8 seconds and peak memory was below 92 MB;
these four tiny fixtures are not a performance benchmark. Platform usage,
pricing, limits, and MCP authentication must be checked for your own account.

## Provenance and references

This is an original extension of the
[pandas join-audit demonstration](https://github.com/JKHUKGY/pandas-join-audit-sample).
Examples use invented sensor records; they are not customer measurements.

- [Apify SDK for Python](https://docs.apify.com/sdk/python/docs/overview)
- [Actor input schema](https://docs.apify.com/actors/development/actor-definition/input-schema)
- [Actor output schema](https://docs.apify.com/actors/development/actor-definition/output-schema)
- [Apify MCP server](https://docs.apify.com/integrations/mcp)
- [pandas merge validation](https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.merge.html)

Author: junzheng jia
