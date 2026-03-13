#!/usr/bin/env node
/**
 * Script de validation des variables d'environnement pour CLEF Frontend.
 *
 * Usage:
 *   node validate-env.js [--env-file .env]
 *
 * Vérifie que toutes les variables d'environnement requises sont définies
 * et ont des valeurs valides.
 */

const fs = require('fs');
const path = require('path');

class EnvValidator {
  constructor(envFile = '.env') {
    this.envFile = envFile;
    this.errors = [];
    this.warnings = [];

    // Variables obligatoires
    this.REQUIRED_VARS = [
      'ENVIRONMENT',
      'API_URL',
      'DOMAIN',
      'GOOGLE_DOMAIN',
      'GOOGLE_CLIENT_ID',
      'GOOGLE_ISSUER',
      'GCP_PROJECT',
    ];

    // Variables optionnelles avec valeurs par défaut
    this.OPTIONAL_VARS = {
      APP_NAME: 'CLEF - Gestion Véhicules',
      APP_SHORT_NAME: 'CLEF',
      THEME_COLOR: '#E30613',
      BACKGROUND_COLOR: '#FFFFFF',
      ENABLE_OFFLINE_MODE: 'true',
      ENABLE_DEBUG_MODE: 'false',
      MAX_PHOTO_SIZE_MB: '10',
      MAX_PHOTOS_PER_FORM: '10',
      CACHE_DURATION_REFERENTIELS: '3600',
      CACHE_DURATION_VEHICULES: '300',
    };

    // Validations spécifiques
    this.VALIDATIONS = {
      ENVIRONMENT: (v) => ['dev', 'test', 'prod'].includes(v),
      GCP_PROJECT: (v) => ['rcq-fr-dev', 'rcq-fr-test', 'rcq-fr-prod'].includes(v),
      API_URL: (v) => v.startsWith('http://') || v.startsWith('https://'),
      GOOGLE_DOMAIN: (v) => v.includes('.okta.com'),
      GOOGLE_ISSUER: (v) => v.startsWith('https://'),
      MAX_PHOTO_SIZE_MB: (v) => !isNaN(parseInt(v)) && parseInt(v) > 0,
      MAX_PHOTOS_PER_FORM: (v) => !isNaN(parseInt(v)) && parseInt(v) > 0,
    };
  }

  loadEnvFile() {
    const envVars = {};

    if (!fs.existsSync(this.envFile)) {
      this.errors.push(`Fichier ${this.envFile} introuvable`);
      return envVars;
    }

    const content = fs.readFileSync(this.envFile, 'utf-8');
    const lines = content.split('\n');

    lines.forEach((line, index) => {
      const trimmed = line.trim();

      // Ignorer les commentaires et lignes vides
      if (!trimmed || trimmed.startsWith('#')) {
        return;
      }

      // Parser la ligne KEY=VALUE
      const equalIndex = trimmed.indexOf('=');
      if (equalIndex > 0) {
        const key = trimmed.substring(0, equalIndex).trim();
        const value = trimmed.substring(equalIndex + 1).trim();
        envVars[key] = value;
      }
    });

    return envVars;
  }

  validate() {
    const envVars = this.loadEnvFile();

    if (this.errors.length > 0) {
      return false;
    }

    // Vérifier les variables obligatoires
    this.REQUIRED_VARS.forEach((varName) => {
      if (!envVars[varName] || envVars[varName] === '') {
        this.errors.push(`Variable obligatoire manquante: ${varName}`);
      } else if (this.VALIDATIONS[varName]) {
        if (!this.VALIDATIONS[varName](envVars[varName])) {
          this.errors.push(`Valeur invalide pour ${varName}: ${envVars[varName]}`);
        }
      }
    });

    // Vérifier les variables optionnelles
    Object.entries(this.OPTIONAL_VARS).forEach(([varName, defaultValue]) => {
      if (!envVars[varName] || envVars[varName] === '') {
        this.warnings.push(
          `Variable optionnelle manquante: ${varName} (défaut: ${defaultValue})`
        );
      }
    });

    // Vérifications spécifiques
    this.checkConsistency(envVars);
    this.checkSecurityVars(envVars);

    return this.errors.length === 0;
  }

  checkConsistency(envVars) {
    // Vérifier la cohérence ENVIRONMENT / GCP_PROJECT
    if (envVars.ENVIRONMENT && envVars.GCP_PROJECT) {
      const expected = `rcq-fr-${envVars.ENVIRONMENT}`;
      if (envVars.GCP_PROJECT !== expected) {
        this.warnings.push(
          `Incohérence: ENVIRONMENT=${envVars.ENVIRONMENT} mais GCP_PROJECT=${envVars.GCP_PROJECT} (attendu: ${expected})`
        );
      }
    }

    // Vérifier que l'API_URL correspond à l'environnement
    if (envVars.ENVIRONMENT === 'dev' && envVars.API_URL) {
      if (!envVars.API_URL.includes('localhost') && !envVars.API_URL.includes('127.0.0.1')) {
        this.warnings.push(
          `En dev, API_URL devrait pointer vers localhost (actuel: ${envVars.API_URL})`
        );
      }
    }
  }

  checkSecurityVars(envVars) {
    if (envVars.ENVIRONMENT === 'prod') {
      if (envVars.ENABLE_DEBUG_MODE === 'true') {
        this.errors.push('ENABLE_DEBUG_MODE ne doit pas être activé en production');
      }
    }
  }

  printReport() {
    console.log('\n' + '='.repeat(70));
    console.log('VALIDATION DES VARIABLES D\'ENVIRONNEMENT - CLEF Frontend');
    console.log('='.repeat(70));

    if (this.errors.length > 0) {
      console.log(`\n❌ ERREURS (${this.errors.length}):`);
      this.errors.forEach((error) => console.log(`  - ${error}`));
    }

    if (this.warnings.length > 0) {
      console.log(`\n⚠️  AVERTISSEMENTS (${this.warnings.length}):`);
      this.warnings.forEach((warning) => console.log(`  - ${warning}`));
    }

    if (this.errors.length === 0 && this.warnings.length === 0) {
      console.log('\n✅ Toutes les variables sont correctement configurées!');
    }

    console.log('\n' + '='.repeat(70) + '\n');
  }
}

// Point d'entrée
function main() {
  const args = process.argv.slice(2);
  let envFile = '.env';

  // Parser les arguments
  for (let i = 0; i < args.length; i++) {
    if (args[i] === '--env-file' && i + 1 < args.length) {
      envFile = args[i + 1];
      i++;
    }
  }

  const validator = new EnvValidator(envFile);
  const isValid = validator.validate();
  validator.printReport();

  process.exit(isValid ? 0 : 1);
}

if (require.main === module) {
  main();
}

module.exports = { EnvValidator };

