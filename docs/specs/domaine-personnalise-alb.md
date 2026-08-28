# Domaine personnalisé par load balancer applicatif global

## Objet

Servir CLEF sur un domaine maîtrisé — `clef.paquerette.com` en dev, vraisemblablement
`clef.croix-rouge.fr` en production — au lieu des URL `*.run.app`, avec un certificat
géré et une politique TLS moderne.

## Décisions, et pourquoi

**Un seul hôte.** Tout passe par `clef.<domaine>` ; la racine offre les deux entrées et
l'utilisateur clique où il veut aller. Décision de l'utilisateur : « c'est plus simple à
retenir ». Conséquence technique : aucune règle d'hôte à maintenir, et le navigateur
reste sur une **même origine** — cookie `SameSite=Lax` suffisant, aucun CORS dans le
parcours normal.

**Routage par chemin, pas par sous-domaine.** Un sous-domaine pour l'API
(`be.clef.…`) a été envisagé puis écarté : il n'était nécessaire que pour permettre au
relais nginx d'atteindre l'API une fois l'ingress verrouillé. Le LB route directement.

**Load balancer plutôt que mappage de domaine Cloud Run.** `gcloud run domain-mappings`
supporte europe-west1 mais reste « preview, not production-ready » selon Google, et
surtout **ne permet pas de désactiver TLS 1.0 et 1.1**. Le LB donne la politique TLS,
et ouvre Cloud Armor et le CDN plus tard. Coût assumé : une règle de transfert globale,
~18 $/mois.

## Table de routage

| Chemin | Service | Raison |
|---|---|---|
| `/api/*` | `clef-api` | routes métier |
| `/auth/*` | `clef-api` | tout le parcours OAuth (`prefix="/auth"`) |
| `/admin/super/*` | `clef-api` | ⚠️ router backend, voir la collision |
| tout le reste | `clef-frontend` | accueil, `/admin/*`, `/form/*`, statiques |

**La collision `/admin`.** `/admin/` est le préfixe de l'application Angular
d'administration, mais `/admin/super` est un router du backend
(`app/admin/super_admin_routes.py`). Les règles de chemin se résolvent par préfixe le
plus long : `/admin/super/*` gagne sur le service par défaut, et `/admin/vehicles`
continue d'aller au frontend.

## Entrées et sorties

**Entrée unique de configuration** — deux endroits, à tenir identiques :

| Où | Variable | Valeur |
|---|---|---|
| `deploy/terraform/environments/<env>.tfvars` | `public_domain` | `clef.paquerette.com` |
| `deploy/deploy.<env>.env` | `PUBLIC_DOMAIN` | `clef.paquerette.com` |

Le premier fait émettre le certificat et pose la règle d'hôte ; le second fait que
l'application connaît son propre nom. `01-gcp-deploy.sh` en dérive **tout** le reste :
`CORS_ORIGINS`, `ALLOWED_FRONTEND_URLS`, `FRONTEND_URL`, `GOOGLE_REDIRECT_URI` et
`DOMAIN`.

**Sorties Terraform** : `load_balancer_ip`, `dns_a_creer` (l'enregistrement prêt à
recopier) et `certificat_verifier` (la commande de suivi).

Laisser `public_domain` vide ne crée **aucune** ressource de LB : test et prod n'en ont
pas encore, et un LB inutile est facturé.

## Critères d'acceptation

- [ ] `tofu validate` et `fmt -check` passent
- [ ] `public_domain` vide ⇒ aucune ressource de LB planifiée
- [ ] L'apply crée l'IP statique et la sortie `dns_a_creer` donne l'enregistrement exact
- [ ] Les six blocs `test` de l'url map sont acceptés par GCP — c'est **la plateforme**
      qui valide le routage, pas notre lecture
- [ ] `https://<domaine>/` sert la page d'accueil, `/admin/` et `/form/` les applications
- [ ] `https://<domaine>/api/test` répond depuis le backend
- [ ] `https://<domaine>/auth/callback` atteint le backend, et le cookie de session est
      posé sur l'hôte public
- [ ] `http://<domaine>/…` redirige en 301 vers `https`, chemin conservé
- [ ] Le certificat passe en `ACTIVE`
- [ ] Une connexion TLS 1.1 est refusée
- [ ] Les QR codes encodent `https://<domaine>/vehicle/<id>`, qui redirige vers
      `/form/vehicle/<id>`

## Ordre d'exploitation

L'ordre n'est pas indicatif : **le certificat managé ne se provisionne que si le domaine
résout déjà vers l'IP du LB.**

1. `./00-infra.sh <env>` → l'IP, via la sortie `dns_a_creer`
2. Enregistrement **A** chez le registrar (pas un CNAME : un ALB global s'atteint par IP)
3. Attendre `ACTIVE` — 15 min en général, 24 h au pire
4. `PUBLIC_DOMAIN` dans `deploy.<env>.env`, puis `./01-gcp-deploy.sh <env>`
5. Console GCP : origine et URI de redirection du domaine sur le client OAuth
6. Facultatif, **après** confirmation : ingress des deux services sur
   `internal-and-cloud-load-balancing`

Un certificat bloqué en `FAILED_NOT_VISIBLE` signifie que le DNS ne résout pas encore
vers la bonne IP.

## Hors périmètre

Cloud Armor, le CDN, l'IPv6, le verrouillage de l'ingress (étape 6, décidée après
observation), et le retrait du relais nginx — qui devient du code mort une fois
l'ingress verrouillé, mais reste le seul chemin tant qu'il ne l'est pas.

## Risques

| Risque | Traitement |
|---|---|
| Le certificat ne se provisionne pas | cause quasi toujours DNS ; la sortie `certificat_verifier` donne la commande de diagnostic |
| Perte de l'IP statique ⇒ reconfiguration DNS et réémission | `prevent_destroy` sur l'adresse |
| `DOMAIN` change après impression de QR codes | les autocollants deviennent invalides. Ne rien imprimer depuis un environnement non définitif — l'utilisateur en est averti et en a convenu |
| Le LB coupe une requête longue | `timeout_sec` de l'API à 300 s, aligné sur le `timeoutSeconds` du service |
