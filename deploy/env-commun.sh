#!/usr/bin/env bash
#
# Fonctions partagées par 00-infra.sh et 01-gcp-deploy.sh — à SOURCER, pas à lancer.
#
# ⚠️ Pourquoi un fichier commun : `deploy/deploy.<env>.env` est l'UNIQUE source des
# variables d'un environnement, et les deux scripts la lisent. Valider le domaine dans
# chacun aurait produit deux règles qui divergent — l'un refusant ce que l'autre
# accepte, sur la valeur qui finit imprimée sur les véhicules.

# Valide un nom d'hôte public et le renvoie en minuscules sur la sortie standard.
# Rend 1 et explique sur stderr si la valeur n'est pas un nom d'hôte seul.
#
# ⚠️ PUBLIC_DOMAIN est utilisé BRUT pour fabriquer les URL de l'application. Une valeur
# collée avec son schéma — « https://dev.clef.paquerette.com », la forme qu'affiche la
# documentation — donnait « https://https://dev.clef… » dans FRONTEND_URL,
# GOOGLE_REDIRECT_URI et, de façon IRRÉVERSIBLE, dans DOMAIN : l'hôte encodé dans les
# QR codes collés sur les véhicules.
valider_domaine_public() {
    local brut="${1:-}" domaine
    domaine="$(printf '%s' "$brut" | tr '[:upper:]' '[:lower:]')"

    if [ -z "$domaine" ]; then
        printf ''
        return 0
    fi

    if ! printf '%s' "$domaine" \
        | grep -Eq '^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$'; then
        {
            echo "❌ Domaine public invalide : « $brut »"
            echo "   Attendu : un nom d'hôte SEUL — « dev.clef.paquerette.com »."
            echo "   Pas de schéma (https://), pas de chemin, pas de port."
        } >&2
        return 1
    fi

    printf '%s' "$domaine"
}

# Charge deploy/deploy.<env>.env — l'unique source des variables d'un environnement.
#
# ⚠️ Terraform n'est PAS une source : `00-infra.sh` lui passe ces valeurs en `-var`.
# Les anciens `deploy/terraform/environments/*.tfvars` portaient project_id, region et
# public_domain en double, et personne ne pensait à aller les y chercher.
charger_env_deploiement() {
    local fichier="deploy/deploy.${1}.env"
    if [ ! -f "$fichier" ]; then
        {
            echo "❌ $fichier absent."
            echo "   Le copier depuis deploy/deploy.env.example et le renseigner :"
            echo "     cp deploy/deploy.env.example $fichier"
        } >&2
        return 1
    fi
    set -a
    # shellcheck disable=SC1090
    . "./$fichier"
    set +a
    # Le chemin sert aux messages d'erreur des appelants.
    # shellcheck disable=SC2034
    ENV_FILE="$fichier"
}
