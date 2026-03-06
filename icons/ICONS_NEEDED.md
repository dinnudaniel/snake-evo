# App Icons Required

Place your app icon files here:

- `icon-192.png` — 192×192px (Android + PWA)
- `icon-512.png` — 512×512px (PWA splash / store listing)

## For iOS (Capacitor generates these automatically from a 1024×1024 source)
After running `npx cap add ios`, use Xcode's asset catalog or a tool like:
- https://appicon.co — paste your 1024×1024 icon, download all sizes

## Quick icon generation
If you have a 1024×1024 source image, run:
```
npx capacitor-assets generate
```
This auto-generates all required sizes for iOS and Android.
