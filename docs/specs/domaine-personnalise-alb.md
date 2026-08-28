# Domaine personnalisé par load balancer applicatif global

## Objet

Servir CLEF sur un domaine maîtrisé, au lieu des URL `*.run.app`, avec un certificat
géré et une politique TLS moderne.

**Un hôte par environnement, préfixé** : `dev.clef.paquerette.com` en dev,
`clef.paquerette.com` — sans préfixe — réservé à la **production**, et
`clef.croix-rouge.fr` si la Croix-Rouge délègue un sous-domaine. Le premier
déploiement du 2026-08-28 a servi dev sur le domaine nu : corrigé le même jour, avant
qu'aucun QR code ne soit imprimé. ⚠️ C'est le vrai enjeu du préfixe — `DOMAIN` est
l'hôte encodé dans les autocollants collés sur les véhicules, et un autocollant ne se
corrige pas par un redéploiement.

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
| `deploy/deploy.<env>.env` | `PUBLIC_DOMAIN` | `dev.clef.paquerette.com` |

**Une seule déclaration.** `00-infra.sh` la passe à Terraform en `-var` — d'où le
certificat et la règle d'hôte — et `01-gcp-deploy.sh` la donne à l'application, qui
apprend ainsi son propre nom.

⚠️ La version initiale en avait **deux** : celle-ci et `public_domain` dans
`deploy/terraform/environments/<env>.tfvars`, « deux endroits à tenir identiques ». Ils
ne l'ont pas été : le 2026-08-28, le domaine de dev a été corrigé d'un seul côté. Les
tfvars sont supprimés — personne ne pense à chercher une valeur d'environnement dans du
code Terraform. `01-gcp-deploy.sh` en dérive **tout** le reste :
`CORS_ORIGINS`, `ALLOWED_FRONTEND_URLS`, `FRONTEND_URL`, `GOOGLE_REDIRECT_URI` et
`DOMAIN`.

**Sorties Terraform** : `load_balancer_ip`, `dns_a_creer` (l'enregistrement prêt à
recopier) et `certificat_verifier` (la commande de suivi).

Laisser `public_domain` vide ne crée **aucune** ressource de LB : test et prod n'en ont
pas encore, et un LB inutile est facturé.

**Une exception, et elle est délibérée** : l'IP statique reste réservée
(`keep_public_ip`, défaut `true`). Le DNS déjà publié reste donc valide, et rallumer le
LB ne demande ni nouvel enregistrement ni réémission de certificat, pour ~7 $/mois. La
libérer est une opération explicite (`keep_public_ip = false`), à ne faire que si le
domaine est abandonné.

`ALLOWED_FRONTEND_URLS` est la seule de ces variables à être une **liste** : le domaine
public d'abord, puis les origines `*.run.app`, qui restent des destinations de connexion
légitimes tant que l'ingress n'est pas verrouillé.

## Critères d'acceptation

- [ ] `tofu validate` et `fmt -check` passent
- [ ] `public_domain` vide ⇒ aucune ressource de LB planifiée
- [ ] L'apply crée l'IP statique et la sortie `dns_a_creer` donne l'enregistrement exact
- [ ] Les six blocs `test` de l'url map sont acceptés par GCP — c'est **la plateforme**
      qui valide le routage, pas notre lecture
- [ ] `https://<domaine>/` sert la page d'accueil, `/admin/` et `/form/` les applications
- [ ] `https://<domaine>/api/test` répond depuis le backend — **et ne divulgue ni
      l'environnement ni le mode mock** : la sonde est publique, le diagnostic est en
      `GET /admin/super/environnement`, sous guard
- [ ] `https://<domaine>/auth/callback` atteint le backend, et le cookie de session est
      posé sur l'hôte public
- [ ] `http://<domaine>/…` redirige en 301 vers `https`, chemin conservé
- [ ] Les trois sondes ci-dessus sont exécutées par `01-gcp-deploy.sh` lui-même, qui
      ne conclut plus « ✅ terminé » quand le domaine ne répond pas
- [ ] `Strict-Transport-Security` est émis par le frontend : un 301 depuis le clair
      reste interceptable à la première visite
- [ ] Le relais nginx couvre les **mêmes** préfixes que le load balancer, `/admin/super`
      compris — sinon ces appels reçoivent l'index.html de l'application admin par
      l'URL run.app
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
5. Console GCP : origine et URI de redirection du domaine sur le client OAuth —
   `01-gcp-deploy.sh` affiche les deux valeurs **réellement déployées** (il affichait
   auparavant l'URI `*.run.app`, ce qui garantissait un `redirect_uri_mismatch`)
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
| Perte de l'IP statique ⇒ reconfiguration DNS et réémission | `prevent_destroy` sur l'adresse, et `keep_public_ip` (défaut `true`) la garde réservée quand le LB est éteint — sans quoi `prevent_destroy` faisait échouer AU PLAN tout apply qui vidait `public_domain`, y compris pour des changements sans rapport |
| `DOMAIN` change après impression de QR codes | les autocollants deviennent invalides. Ne rien imprimer depuis un environnement non définitif — l'utilisateur en est averti et en a convenu |
| Le LB coupe une requête longue | **Rien à régler ici, et surtout PAS `timeout_sec`** : GCP le REFUSE sur un backend service adossé à un NEG serverless (`Error 400: Timeout sec is not supported…`). Le délai effectif est le `timeoutSeconds` du service Cloud Run. La version initiale de cette spec prescrivait 300 s ici — c'était faux, et l'apply échouait |
| Changement de domaine ⇒ le certificat doit être remplacé sans coupure | Le nom du certificat porte `substr(sha256(public_domain), 0, 8)`. Avec un nom fixe, `create_before_destroy` ne peut pas fonctionner : GCP refuse le doublon de nom (`alreadyExists`). **Ne jamais composer ce nom à la main** — utiliser la sortie `certificat_verifier` |
| L'origine `*.run.app` cesse d'être une destination de connexion valide | `ALLOWED_FRONTEND_URLS` est une **liste** : le domaine public en tête, les URL run.app conservées derrière. Ces services restent publiquement invocables tant que l'ingress n'est pas verrouillé (étape 6) |
| `PUBLIC_DOMAIN` collé avec son schéma | Les DEUX scripts refusent avant d'agir, par la même fonction `valider_domaine_public` de `deploy/env-commun.sh` : la valeur alimente le certificat et les URL de l'application, deux règles distinctes auraient fini par diverger |
