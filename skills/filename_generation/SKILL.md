# Filename Generation Rules

## Default Template
{tags}_{index}

## Template Variables
- {tags} — underscore-joined semantic tags from classifier/vision
- {index} — zero-padded 2-digit index
- {date} — best-available date from metadata
- {ext} — original file extension
- {summary} — first 30 chars of metadata summary

## Sanitization Rules
- Replace invalid chars (<>:"/\|?*) with underscore
- Replace whitespace with underscore
- Max 200 chars for basename
- Force lowercase
- Strip leading/trailing dots and underscores
