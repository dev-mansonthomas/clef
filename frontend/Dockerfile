# Production Dockerfile for CLEF Frontend
# Multi-stage build for both admin and form apps

FROM node:22-alpine AS builder

# Set working directory
WORKDIR /app

# Install Angular CLI globally
RUN npm install -g @angular/cli@21

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci --only=production

# Copy application code
COPY . .

# Build both applications for production
RUN ng build admin --configuration production
RUN ng build form --configuration production

# Production stage with nginx
FROM nginx:alpine

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/nginx.conf

# Copy built applications
COPY --from=builder /app/dist/admin/browser /usr/share/nginx/html/admin
COPY --from=builder /app/dist/form/browser /usr/share/nginx/html/form

# Create a simple index.html at root
RUN echo '<html><body><h1>CLEF Fleet Management</h1><ul><li><a href="/admin">Admin App</a></li><li><a href="/form">Form App</a></li></ul></body></html>' > /usr/share/nginx/html/index.html

# Expose port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost/health || exit 1

# Start nginx
CMD ["nginx", "-g", "daemon off;"]

