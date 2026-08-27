# Production Dockerfile for CLEF Frontend
# Multi-stage build for both admin and form apps

FROM node:24-alpine AS builder

# Set working directory
WORKDIR /app

# Copy package files
COPY package*.json ./

# ⚠️ `npm ci` complet, PAS `--only=production` ni `--omit=dev`.
#
# Construire une application Angular EXIGE les devDependencies : le builder
# `@angular/build:application` déclaré dans angular.json, `@angular/compiler-cli` et
# `typescript` y vivent tous les trois. Avec `--only=production`, l'installation
# réussit, puis `ng build` échoue faute de builder — un échec tardif, au milieu d'un
# Cloud Build, dont la cause est deux étapes plus haut.
#
# Ce sont des dépendances de l'étage de CONSTRUCTION : rien de tout cela n'atteint
# l'image finale, qui ne contient que nginx et des fichiers statiques.
RUN npm ci

# Copy application code
COPY . .

# Build both applications for production
#
# `npx ng` et non un `ng` installé globalement : la version du CLI vient alors du
# package.json du projet, la même que celle avec laquelle les builds sont vérifiés
# en local. Un `npm install -g @angular/cli@21` pouvait résoudre un autre patch.
RUN npx ng build admin --configuration production
RUN npx ng build form --configuration production

# Production stage with nginx
FROM nginx:alpine

# Configuration nginx : un GABARIT, pas un fichier figé.
#
# L'entrypoint de l'image nginx traite /etc/nginx/templates/*.template avec envsubst
# au démarrage du conteneur, et écrit le résultat dans /etc/nginx/conf.d/. C'est
# ainsi que ${BACKEND_HOST} est résolu à l'exécution : la même image sert dev, test
# et prod, et l'URL du backend n'est pas gravée dans l'image.
#
# On garde donc le /etc/nginx/nginx.conf de l'image, qui inclut conf.d/*.conf — et
# on supprime son default.conf, qui déclare lui aussi un serveur sur le port 80.
COPY clef.conf.template /etc/nginx/templates/clef.conf.template
RUN rm -f /etc/nginx/conf.d/default.conf

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

