# Image Classification Heuristics

## Rules
- If no EXIF camera data AND dimensions >= 1920x1080 → wallpaper
- If EXIF camera data present → photo
- If dimensions exactly match common screen resolutions (1920x1080, 2560x1440, etc.) AND no EXIF camera → screenshot
- If dimensions between 200-800px AND no EXIF camera → meme
- Multi-label: files can be both "image" and "wallpaper"

## Examples
- 3840x2160, no camera → wallpaper
- 4000x3000, Canon EOS → photo
- 1920x1080, no camera → screenshot
- 512x512, no camera → meme

## Constraints
- Classification is heuristic, not AI. Low-confidence files (<0.6) may be sent to Vision Router if enabled.
