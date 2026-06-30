# Multi-Source Candidate Data Transformer

A Python-based data transformation pipeline that consolidates candidate information from multiple heterogeneous sources into a single canonical candidate profile.

The pipeline parses, normalizes, validates, and merges candidate data while preserving field-level provenance and confidence scores. The final output is a configurable canonical JSON profile suitable for downstream recruiting systems.

---

## Features

- Parse candidate data from multiple sources
  - Recruiter CSV (Structured Source)
  - GitHub Profile URL via GitHub REST API (Unstructured Source)
- Normalize candidate information
  - Names
  - Email addresses
  - Phone numbers
  - Skills
- Merge duplicate candidate records
- Resolve field conflicts using configurable source priority
- Preserve field-level provenance
- Calculate confidence scores
- Generate configurable canonical JSON output
- Handle common real-world data inconsistencies such as:
  - Duplicate records
  - Missing values
  - Invalid emails
  - Invalid phone numbers
  - Different CSV column names

---

## Project Structure

```
candidate-transformer/
├── config/
│   ├── default.json
│   └── custom.json
├── input/
│   └── recruiter.csv
├── output/
├── src/
│   ├── fetchers/
│   ├── mergers/
│   ├── models/
│   ├── normalizers/
│   ├── parsers/
│   ├── utils/
│   └── validators/
├── tests/
├── main.py
├── requirements.txt
├── README.md
└── TECHNICAL_DESIGN.md
```

---

## Requirements

- Python 3.12 or later

Install the required dependencies:

```bash
pip install -r requirements.txt
```

---

## Running the Project

Execute the pipeline using a recruiter CSV file and a GitHub profile URL.

### Windows

```bash
python main.py ^
  --csv input/recruiter.csv ^
  --github-url https://github.com/<github-username> ^
  --config config/default.json
```

### Linux / macOS

```bash
python main.py \
  --csv input/recruiter.csv \
  --github-url https://github.com/<github-username> \
  --config config/default.json
```



---

## Output

The generated candidate profiles are saved in the `output/` directory as timestamped JSON files.

Example:

```
output/candidates_YYYYMMDD_HHMMSS.json
```

Each canonical candidate profile contains:

- Candidate ID
- Full Name
- Email Addresses
- Phone Numbers
- Location
- Social Links
- Skills
- Experience
- Education
- Provenance Metadata
- Confidence Scores

---

## Running Tests

```bash
python -m pytest tests -v
```

---

## Technical Design

Detailed information about the system architecture, parsing workflow, normalization strategy, merge logic, provenance tracking, confidence calculation, runtime configuration, assumptions, and limitations is available in:

```
TECHNICAL_DESIGN.md
```

