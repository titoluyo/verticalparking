# Logo Printing Analysis

## Current Logo Properties

- **File**: `vertical_parking_logo.png`
- **Dimensions**: 3584 x 1184 pixels
- **Color Mode**: RGB
- **Format**: PNG

## Printer Requirements

The Cashino KP-300 is an 80mm thermal printer with the following specifications:

- **Maximum Print Width**: 384 pixels (at 203 DPI) or 576 pixels (at 300 DPI)
- **Color Support**: Monochrome (grayscale/black & white only)
- **Image Format**: PNG, JPEG (converted to grayscale internally)

## Required Modifications

### 1. **Resize to Fit Printer Width**

The logo is currently **3584 pixels wide**, which is **9.3x larger** than the maximum printer width (384 pixels).

**Required Action**: Resize the image to a maximum width of **384 pixels** while maintaining aspect ratio.

**Calculation**:
- Original: 3584 x 1184 pixels
- Aspect ratio: 3584 / 1184 = 3.027
- New width: 384 pixels
- New height: 384 / 3.027 = **127 pixels** (rounded)

**Result**: Logo should be resized to **384 x 127 pixels** for optimal printing.

### 2. **Convert to Grayscale**

Thermal printers only print in monochrome. The logo is currently in RGB mode.

**Required Action**: Convert the image to grayscale (mode 'L') or 1-bit (mode '1') for best results.

**Recommendation**: 
- Use grayscale ('L') for smoother gradients and better detail preservation
- Use 1-bit ('1') for pure black/white with maximum contrast (may lose some detail)

### 3. **Image Processing Steps**

The test script (`test_printer.py`) now includes Test 14 which automatically:

1. ✅ Loads the logo file
2. ✅ Resizes to 384 pixels width (maintaining aspect ratio)
3. ✅ Converts to grayscale
4. ✅ Prints with center alignment
5. ✅ Uses high-density printing for best quality

## Testing the Logo Print

Run the test script to print the logo:

```bash
cd kiosko
python test_printer.py
```

The script will:
- Automatically resize the logo to fit the printer
- Convert it to grayscale
- Print it with optimal settings
- Show diagnostic information in the console

## Manual Image Preparation (Optional)

If you want to pre-process the logo manually, you can use Python:

```python
from PIL import Image

# Load original logo
img = Image.open('vertical_parking_logo.png')

# Resize to fit 80mm printer (384px width)
max_width = 384
ratio = max_width / img.size[0]
new_size = (max_width, int(img.size[1] * ratio))
resized = img.resize(new_size, Image.Resampling.LANCZOS)

# Convert to grayscale
grayscale = resized.convert('L')

# Optional: Convert to 1-bit for pure black/white
# bw = grayscale.convert('1')

# Save processed version
grayscale.save('vertical_parking_logo_processed.png')
```

## Expected Print Quality

- **Width**: Will fill the full 80mm paper width
- **Height**: Approximately 33mm (127 pixels at 203 DPI)
- **Quality**: High-density printing for crisp, clear output
- **Contrast**: Good (grayscale conversion preserves detail)

## Notes

- The logo's black and white design is ideal for thermal printing
- The text "VERTICAL PARKING AUTOMATED SYSTEMS" should print clearly
- The stacked car graphic should be recognizable
- Center alignment ensures the logo is centered on the ticket

## Integration into Ticket Design

To use the logo in actual tickets (see `app/printer.py`), you can add:

```python
from PIL import Image

# Load and prepare logo
logo = Image.open('vertical_parking_logo.png')
logo = logo.resize((384, int(logo.size[1] * (384 / logo.size[0]))), Image.Resampling.LANCZOS)
logo = logo.convert('L')

# Print logo at the top of ticket
p.image(logo, center=True, high_density_vertical=True, high_density_horizontal=True)
p.text("\n")
```

