# QR Code Generator Component

Component for generating and printing QR codes for vehicles in the CLEF admin application.

## Overview

This component generates QR codes for each vehicle based on their `nom_synthetique` field. The QR codes encode URLs that point to the form application, allowing volunteers to quickly access the vehicle check-in/check-out form by scanning the code.

## Features

- **Automatic QR Code Generation**: Generates QR codes for all vehicles accessible to the current user
- **Print Functionality**:
  - Print all QR codes at once
  - Print individual QR codes
  - Optimized for A4 paper format with 6 QR codes per page (2x3 grid)
- **Responsive Design**: Grid layout for screen viewing, optimized print layout for paper
- **Material Design**: Uses Angular Material components for consistent UI
- **Instruction Message**: Displays "À la prise et au retour du véhicule, veuillez remplir le formulaire CLEF" on each QR code

## Usage

### Accessing the Component

Navigate to `/qr-codes` in the admin application.

### Printing QR Codes

1. **Print All**: Click the "Imprimer tous les QR codes" button to print all vehicle QR codes
2. **Print Single**: Click the "Imprimer" button on an individual card to print just that vehicle's QR code

### Print Settings

The component is optimized for **A4 portrait** format with 10mm margins, displaying **6 QR codes per page** in a 2x3 grid layout.

**Layout Details:**
- Grid: 2 columns × 3 rows
- Gap between QR codes: 8mm
- Each QR code: 100px × 100px
- Dashed border around each QR code as a cutting guide
- Page break after every 6 QR codes

The print layout automatically hides the sidebar and header to maximize space for QR codes.

## QR Code URL Format

The QR codes encode URLs in the following format:

```
https://{DOMAIN}/vehicle/{encoded_id}
```

Where:
- `{DOMAIN}` is the form application domain (e.g., `clef.example.com`)
- `{encoded_id}` is the vehicle identifier encoded with SALT

### Current Implementation

Currently uses **base64 encoding** of the `nom_synthetique` as a placeholder:

```typescript
const encodedId = btoa(nomSynthetique);
```

### Production Implementation

In production, the encoding should use the backend SALT for security:

1. Create a backend endpoint: `POST /api/vehicles/encode`
2. Backend hashes `nom_synthetique + SALT` using a secure algorithm (e.g., SHA-256)
3. Update `QrCodeService.encodeVehicleId()` to call this endpoint
4. Form application decodes using the same SALT

## Files

- `qr-code-generator.component.ts` - Main component logic
- `qr-code-generator.component.html` - Template with screen and print layouts
- `qr-code-generator.component.scss` - Styles including print media queries
- `qr-code-generator.component.spec.ts` - Unit tests
- `qr-code.service.ts` - Service for QR code URL generation
- `qr-code.service.spec.ts` - Service unit tests
- `qr-code-test.html` - Standalone test page for QR code generation

## Dependencies

- `angularx-qrcode` (v21.0.4) - QR code generation library
- Angular Material - UI components
- RxJS - Reactive programming

## Testing

### Unit Tests

Run unit tests:

```bash
cd frontend
npm test -- --project=admin
```

### Manual Testing

1. Open `qr-code-test.html` in a browser to see a standalone QR code example
2. Test print functionality with browser's print preview
3. Scan generated QR code with a mobile device to verify URL

## Future Enhancements

1. **Backend SALT Integration**: Replace base64 encoding with secure hashing
2. **Batch Download**: Export QR codes as PDF or images
3. **Customization**: Allow users to configure QR code size and error correction level
4. **Vehicle Filtering**: Add filters to generate QR codes for specific ULs or vehicle types
5. **QR Code Configuration**: Per-vehicle settings (prise seule, retour seul, les deux)

