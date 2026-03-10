#!/usr/bin/env node

/**
 * Simple PWA icon generator
 * Creates placeholder icons for both admin and form apps
 */

const fs = require('fs');
const path = require('path');

// SVG template for icons
const createSVG = (text, color, size) => `<?xml version="1.0" encoding="UTF-8"?>
<svg width="${size}" height="${size}" xmlns="http://www.w3.org/2000/svg">
  <rect width="${size}" height="${size}" fill="${color}"/>
  <text x="50%" y="50%" font-family="Arial, sans-serif" font-size="${size * 0.3}" 
        fill="white" text-anchor="middle" dominant-baseline="middle" font-weight="bold">
    ${text}
  </text>
</svg>`;

const apps = [
  {
    name: 'admin',
    path: 'projects/admin/public',
    text: 'CLEF\nAdmin',
    color: '#e30613'
  },
  {
    name: 'form',
    path: 'projects/form/public',
    text: 'CLEF\nForm',
    color: '#e30613'
  }
];

const sizes = [192, 512];

console.log('Generating PWA icons...\n');

apps.forEach(app => {
  const publicDir = path.join(__dirname, app.path);
  
  if (!fs.existsSync(publicDir)) {
    fs.mkdirSync(publicDir, { recursive: true });
  }

  sizes.forEach(size => {
    const svgContent = createSVG(app.text, app.color, size);
    const filename = `icon-${size}x${size}.svg`;
    const filepath = path.join(publicDir, filename);
    
    fs.writeFileSync(filepath, svgContent);
    console.log(`✓ Created ${app.name}/${filename}`);
  });
});

console.log('\n✓ PWA icons generated successfully!');
console.log('\nNote: For production, replace these SVG files with proper PNG icons.');
console.log('You can use tools like:');
console.log('  - https://realfavicongenerator.net/');
console.log('  - https://www.pwabuilder.com/imageGenerator');

