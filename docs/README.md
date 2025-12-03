# Documentation Directory

This directory contains technical documentation for significant changes, fixes, and architectural decisions in the Chromecast radio project.

## Files

### kozt_lite_fixes.md
Documents the cleanup improvements made to `kozt_lite.py` to fix PyInstaller `--onefile` binary issues where the Chromecast receiver wasn't properly stopped on program termination.

**Key Changes:**
- Added zeroconf cleanup
- Added atexit handler for PyInstaller
- Unified zeroconf management
- Improved signal handling

### play_kozt_fixes.md
Documents the same cleanup improvements applied to `play_kozt.py` (the custom receiver version). The fixes are identical to `kozt_lite.py` but work alongside the additional custom receiver features.

## Documentation Guidelines

When making significant changes to the codebase:

1. **Create a new markdown file** in this directory documenting:
   - The problem being solved
   - Root causes identified
   - Changes made (with technical details)
   - Testing procedures
   - Related changes or dependencies

2. **Update this README.md** with a brief summary of the new file

3. **Include documentation in commits** - Add docs files to the same commit as the code changes when possible

4. **Cross-reference** - Link related documentation files together

## Naming Convention

Use descriptive names that indicate:
- Which file(s) are affected
- What type of change (fixes, features, refactoring)

Examples:
- `kozt_lite_fixes.md` - Fixes for kozt_lite.py
- `pixel_tablet_hub_mode.md` - Feature documentation for Pixel Tablet support
- `metadata_architecture.md` - Architectural overview of metadata system
