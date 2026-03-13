#!/usr/bin/env python3
"""
Script de validation des variables d'environnement pour CLEF Backend.

Usage:
    python validate_env.py [--env-file .env]

Vérifie que toutes les variables d'environnement requises sont définies
et ont des valeurs valides.
"""

import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
import re


class EnvValidator:
    """Validateur de variables d'environnement."""

    # Variables obligatoires
    REQUIRED_VARS = [
        "ENVIRONMENT",
        "GCP_PROJECT",
        "GCP_REGION",
        "GCP_RESOURCE_PREFIX",
        "DOMAIN",
        "REDIS_URL",
        "SHEETS_URL_VEHICULES",
        "SHEETS_URL_BENEVOLES",
        "SHEETS_URL_RESPONSABLES",
        "GOOGLE_DOMAIN",
        "GOOGLE_CLIENT_ID",
        "GOOGLE_CLIENT_SECRET",
        "GOOGLE_ISSUER",
        "SERVICE_ACCOUNT_EMAIL",
        "EMAIL_GESTIONNAIRE_DT",
        "QR_CODE_SALT",
        "CORS_ORIGINS",
    ]

    # Variables optionnelles avec valeurs par défaut
    OPTIONAL_VARS = {
        "CACHE_TTL_REFERENTIELS": "31536000",
        "ALERT_DELAY_DAYS": "60",
        "LOG_LEVEL": "INFO",
        "LOG_FORMAT": "json",
        "PORT": "8000",
        "DEBUG": "false",
    }

    # Validations spécifiques
    VALIDATIONS = {
        "ENVIRONMENT": lambda v: v in ["dev", "test", "prod"],
        "GCP_PROJECT": lambda v: v in ["rcq-fr-dev", "rcq-fr-test", "rcq-fr-prod"],
        "GCP_RESOURCE_PREFIX": lambda v: v == "clef-",
        "REDIS_URL": lambda v: v.startswith("redis://"),
        "SHEETS_URL_VEHICULES": lambda v: "docs.google.com/spreadsheets" in v,
        "SHEETS_URL_BENEVOLES": lambda v: "docs.google.com/spreadsheets" in v,
        "SHEETS_URL_RESPONSABLES": lambda v: "docs.google.com/spreadsheets" in v,
        "GOOGLE_DOMAIN": lambda v: ".okta.com" in v,
        "GOOGLE_ISSUER": lambda v: v.startswith("https://"),
        "EMAIL_GESTIONNAIRE_DT": lambda v: "@croix-rouge.fr" in v,
        "QR_CODE_SALT": lambda v: len(v) >= 16 and v != "CHANGE_ME_TO_RANDOM_STRING_IN_PRODUCTION",
    }

    def __init__(self, env_file: Optional[Path] = None):
        """Initialise le validateur."""
        self.env_file = env_file or Path(".env")
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def load_env_file(self) -> Dict[str, str]:
        """Charge les variables depuis le fichier .env."""
        env_vars = {}
        if not self.env_file.exists():
            self.errors.append(f"Fichier {self.env_file} introuvable")
            return env_vars

        with open(self.env_file, "r") as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                # Ignorer les commentaires et lignes vides
                if not line or line.startswith("#"):
                    continue

                # Parser la ligne KEY=VALUE
                if "=" in line:
                    key, value = line.split("=", 1)
                    env_vars[key.strip()] = value.strip()

        return env_vars

    def validate(self) -> bool:
        """Valide les variables d'environnement."""
        env_vars = self.load_env_file()

        if self.errors:
            return False

        # Vérifier les variables obligatoires
        for var in self.REQUIRED_VARS:
            if var not in env_vars or not env_vars[var]:
                self.errors.append(f"Variable obligatoire manquante: {var}")
            elif var in self.VALIDATIONS:
                if not self.VALIDATIONS[var](env_vars[var]):
                    self.errors.append(f"Valeur invalide pour {var}: {env_vars[var]}")

        # Vérifier les variables optionnelles
        for var, default in self.OPTIONAL_VARS.items():
            if var not in env_vars or not env_vars[var]:
                self.warnings.append(f"Variable optionnelle manquante: {var} (défaut: {default})")

        # Vérifications spécifiques
        self._check_gcp_consistency(env_vars)
        self._check_security_vars(env_vars)

        return len(self.errors) == 0

    def _check_gcp_consistency(self, env_vars: Dict[str, str]):
        """Vérifie la cohérence des variables GCP."""
        if "ENVIRONMENT" in env_vars and "GCP_PROJECT" in env_vars:
            env = env_vars["ENVIRONMENT"]
            project = env_vars["GCP_PROJECT"]
            expected = f"rcq-fr-{env}"
            if project != expected:
                self.warnings.append(
                    f"Incohérence: ENVIRONMENT={env} mais GCP_PROJECT={project} "
                    f"(attendu: {expected})"
                )

    def _check_security_vars(self, env_vars: Dict[str, str]):
        """Vérifie les variables de sécurité."""
        if env_vars.get("ENVIRONMENT") == "prod":
            if env_vars.get("DEBUG", "false").lower() == "true":
                self.errors.append("DEBUG ne doit pas être activé en production")

            if env_vars.get("LOG_LEVEL") == "DEBUG":
                self.warnings.append("LOG_LEVEL=DEBUG n'est pas recommandé en production")

    def print_report(self):
        """Affiche le rapport de validation."""
        print("\n" + "=" * 70)
        print("VALIDATION DES VARIABLES D'ENVIRONNEMENT - CLEF Backend")
        print("=" * 70)

        if self.errors:
            print(f"\n❌ ERREURS ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print(f"\n⚠️  AVERTISSEMENTS ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")

        if not self.errors and not self.warnings:
            print("\n✅ Toutes les variables sont correctement configurées!")

        print("\n" + "=" * 70 + "\n")


def main():
    """Point d'entrée du script."""
    import argparse

    parser = argparse.ArgumentParser(description="Valide les variables d'environnement CLEF")
    parser.add_argument(
        "--env-file",
        type=Path,
        default=Path(".env"),
        help="Chemin vers le fichier .env (défaut: .env)",
    )
    args = parser.parse_args()

    validator = EnvValidator(args.env_file)
    is_valid = validator.validate()
    validator.print_report()

    sys.exit(0 if is_valid else 1)


if __name__ == "__main__":
    main()

