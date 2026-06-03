# Safety Validation Rules

## OS-Safe Filenames
- Strip: < > : " / \ | ? *
- Reserved names (Windows): CON, PRN, AUX, NUL, COM1-9, LPT1-9
- Max path length: 255 characters

## Conflict Prevention
- Detect duplicate proposed names → auto-index
- Never overwrite existing files
- Source must exist before rename

## Reversibility
- Every rename creates undo entry
- Undo restores original name at original path
- Undo sessions stored in ~/.smart_renamer/undo/
