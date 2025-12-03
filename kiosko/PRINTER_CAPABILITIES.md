# Cashino KP-300 Printer Capabilities

This document lists tested capabilities of the Cashino KP-300 thermal printer via ICS Advent Parallel Adapter (USB ID: 0fe6:811e).

## ✅ Working Features

### Text Formatting
- **Fonts**: A (default), B ✅
- **Font C**: ❌ Not supported
- **Bold**: ✅ Works
- **Underline**: ✅ Works
- **Double Width**: ✅ Works
- **Double Height**: ✅ Works
- **Combined Styles**: ✅ Works (bold + double width/height)

### Alignment
- **Left**: ✅ Works
- **Center**: ✅ Works (with warning about pixel width, but functional)
- **Right**: ✅ Works

### Character Encodings
- **CP850**: ✅ Works (supports Spanish: á é í ó ú ñ)
- **PC437**: ❌ Failed
- **LATIN1**: ❌ Failed

### QR Codes
- **All Sizes**: ✅ Works (4, 6, 8, 10)
- **All Error Correction Levels**: ✅ Works (L, M, Q, H)
- **Note**: Center alignment warning appears but QR codes print correctly

### Barcodes
- **EAN13**: ✅ Works
- **EAN8**: ✅ Works
- **CODE39**: ✅ Works
- **ITF**: ✅ Works
- **CODE128**: ⚠️ Format sensitive (requires valid CODE128 format)

### Special Characters
- **Working**: © ® £ ¥ ± × ÷
- **Not Working**: ™ € ≠ ≤ ≥ (appear as question marks)

### Other Features
- **Paper Feed**: ✅ Works
- **Paper Cut**: ✅ Works
- **Line Spacing**: ✅ Works (but visual difference may be minimal)

## ❌ Not Working / Limitations

1. **Font C** - Not supported by printer
2. **PC437 and LATIN1 encodings** - Use CP850 instead
3. **Some Unicode symbols** - ™ € ≠ ≤ ≥ not supported
4. **Line spacing** - Works but visual difference is minimal
5. **QR center alignment** - Warning appears but doesn't affect functionality

## 📝 Recommendations for Implementation

### Use:
- Font A or B (A is default, B for emphasis)
- CP850 encoding for Spanish characters
- Bold, underline, double width/height for emphasis
- QR codes with size 6-8 for good readability
- QR error correction level 0 (L) for simple text, 1-2 for URLs
- EAN13, EAN8, CODE39, ITF barcodes
- Left/center/right alignment

### Avoid:
- Font C
- PC437 and LATIN1 encodings
- Unicode symbols that don't render (™ € ≠ ≤ ≥)
- CODE128 unless you verify the data format is correct

### Notes:
- QR code center alignment warnings can be ignored
- Line spacing works but may not be visually significant
- Always use CP850 encoding when printing Spanish text

