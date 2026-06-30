"""
normalizers/skill_normalizer.py

Canonicalizes skill names and removes duplicates.

Strategy:
- Strip whitespace
- Title-case each skill (so "python" -> "Python")
- Apply a synonym map to unify aliases
- Deduplicate case-insensitively
"""

from __future__ import annotations

# Maps normalized lowercase variant -> canonical display name
SKILL_SYNONYMS: dict[str, str] = {
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "machine-learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "dl": "Deep Learning",
    "deep learning": "Deep Learning",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "js": "JavaScript",
    "javascript": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "py": "Python",
    "python": "Python",
    "node": "Node.js",
    "node.js": "Node.js",
    "nodejs": "Node.js",
    "tensorflow": "TensorFlow",
    "tf": "TensorFlow",
    "pytorch": "PyTorch",
    "sql": "SQL",
    "nosql": "NoSQL",
    "golang": "Go",
    "go": "Go",
    "r": "R",
}


def canonicalize_skill(raw: str) -> str:
    """
    Return the canonical display name for a skill.
    Falls back to title-case if no synonym is found.
    """
    key = raw.strip().lower()
    return SKILL_SYNONYMS.get(key, raw.strip().title())


def normalize_skills(raw_skills: list[str]) -> list[str]:
    """
    Canonicalize and deduplicate a list of skill strings.

    Args:
        raw_skills: Raw skill names from any source.

    Returns:
        Sorted list of unique canonical skill names.
    """
    seen: set[str] = set()
    result: list[str] = []
    for skill in raw_skills:
        if not skill or not skill.strip():
            continue
        canonical = canonicalize_skill(skill)
        key = canonical.lower()
        if key not in seen:
            seen.add(key)
            result.append(canonical)
    return sorted(result)
