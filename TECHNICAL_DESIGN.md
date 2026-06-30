# Technical Design Document — Multi-Source Candidate Data Transformer

## 1. Architecture



```
                  +---------------------------+
                  |      Recruiter CSV        |
                  |    (Structured Source)    |
                  +-------------+-------------+
                                |
                                v
                  +---------------------------+
                  |        csv_parser         |
                  +-------------+-------------+
                                |
                                |
+---------------------------+   |
|     GitHub Profile URL    |   |
|   (Unstructured Source)   |   |
+-------------+-------------+   |
              |                 |
              v                 |
+---------------------------+   |
|     github_fetcher        |   |
|    (GitHub REST API)      |   |
+-------------+-------------+   |
              |                 |
              v                 |
+---------------------------+   |
|      github_parser        |   |
+-------------+-------------+   |
              |                 |
              +--------+--------+
                       |
                       v
         +-------------------------------+
         |       candidate_merger        |
         |  - Group Candidate Records    |
         |  - Resolve Conflicts          |
         |  - Track Provenance           |
         +---------------+---------------+
                         |
                         v
         +-------------------------------+
         |     CanonicalCandidate        |
         |    Internal Data Model        |
         +---------------+---------------+
                         |
                         v
         +-------------------------------+
         |      output_projector         |
         |    Apply OutputConfig         |
         +---------------+---------------+
                         |
                         v
              JSON Output (Console + File)
```

`main.py` (CLI) orchestrates the complete workflow:

**Fetch → Parse → Merge → Project → Output**

---

## 2. Pipeline

1. **Fetch Unstructured Source:** `fetchers/github_fetcher.py` accepts a GitHub profile URL, retrieves profile information and repositories using the GitHub REST API, and converts the response into a format suitable for parsing.

2. **Parse:** `parsers/csv_parser.py` reads the recruiter CSV while `parsers/github_parser.py` processes the fetched GitHub profile. Both parsers normalize emails, phone numbers, skills, and candidate attributes before producing standardized intermediate records with source and confidence metadata.

3. **Merge:** `mergers/candidate_merger.py` groups records using normalized email as the primary identifier and normalized candidate name as a fallback when email is unavailable. Each group is merged into a single `CanonicalCandidate`, while preserving provenance and confidence information.

4. **Project:** `utils/output_projector.py` reads the immutable `CanonicalCandidate` object and applies the user-defined `OutputConfig` without modifying the canonical representation.

5. **Output:** `main.py` prints the final JSON array and writes the generated candidate profiles into the `output/` directory.

---

## 3. Normalization Strategy

| Field | Rule |
|--------|------|
| Name | trimmed, multiple recruiter column names supported (`name`, `full_name`, `candidate_name`) |
| Email | lowercase, trimmed, validated via regex, deduplicated |
| Phone | parsed using the `phonenumbers` library into E.164 format |
| Skills | normalized, deduplicated, title-cased, aggregated from GitHub repositories |
| Candidate Identity | matched using normalized email with normalized name fallback |

Normalization occurs inside the parsers so downstream components always operate on clean, standardized data.

---

## 4. Conflict Resolution

Records are grouped using **normalized email** as the primary identity key. Since GitHub public profiles frequently do not expose email addresses, the merger falls back to **normalized candidate names** when email is unavailable.

Within each candidate group, scalar fields are resolved using the source priority:

**Recruiter CSV > GitHub**

The first available value from the highest-priority source is selected. Collection fields such as emails, phone numbers, skills, links, and experience are aggregated and deduplicated across all contributing sources. Structured fields preserve provenance information for every merged attribute.

---

## 5. Confidence Calculation

Each source is assigned a fixed confidence score:

- Recruiter CSV = **0.95**
- GitHub = **0.80**

Each resolved field inherits the confidence of its originating source. Field confidences are stored internally, while the candidate's `overall_confidence` is calculated as the simple average of all resolved field confidences.

---

## 6. Provenance

Every resolved field generates a `ProvenanceEntry { field, source, method }`.

Supported merge methods are:

- **direct** – only one source supplied the value.
- **priority merge** – multiple sources supplied conflicting values and source priority determined the winner.
- **aggregated** – values from multiple sources were combined.

Provenance is represented as a flat list within the canonical output and can be enabled or disabled through the runtime output configuration.

---

## 7. Edge Cases Handled

- Supports multiple recruiter CSV column names (e.g., `name`, `full_name`, `candidate_name`, `candidate_email`, `email_address`).
- Missing or malformed CSV columns generate warnings without terminating execution.
- Empty recruiter CSV or unavailable GitHub profile produces an empty candidate list instead of a runtime failure.
- Invalid email addresses are ignored while preserving the remaining candidate information.
- Invalid phone numbers are discarded after validation.
- Duplicate recruiter records are merged into a single canonical profile.
- Candidate records with hidden GitHub email addresses are matched using normalized candidate names.
- Email normalization removes duplicate addresses regardless of letter casing.
- Skills extracted from multiple repositories are normalized and deduplicated.
- Empty collections (skills, experience, education) are emitted as empty arrays rather than null values.

---

## 8. Out of Scope

- LinkedIn profile scraping.
- Resume PDF parsing.
- OCR-based candidate extraction.
- AI-based semantic or fuzzy entity resolution beyond deterministic name fallback.
- Automatic education extraction from unstructured text.
- Persistent database storage for incremental candidate updates.