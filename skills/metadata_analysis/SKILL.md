# Metadata Analysis Rules

## Date Priority
1. EXIF DateTimeOriginal
2. File creation date (ctime)
3. File modification date (mtime)

## GPS Handling
- Extract from EXIF GPSInfo tag
- Convert DMS to decimal degrees
- Skip if coords are (0,0) or clearly invalid

## Camera
- Concatenate Make + Model from EXIF
- Use first word as tag (e.g., "canon" from "Canon EOS 5D")
