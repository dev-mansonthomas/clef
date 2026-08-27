# Load balancer applicatif externe global, devant les deux services Cloud Run.
#
# ─── Pourquoi un LB plutôt qu'un mappage de domaine Cloud Run ─────────────────
#
# `gcloud run domain-mappings` existe et supporte europe-west1, mais Google le donne
# pour « preview, not production-ready », et surtout **TLS 1.0 et 1.1 ne peuvent pas y
# être désactivés**. Ici la politique SSL impose TLS 1.2 au minimum. Le LB permet en
# outre Cloud Armor et le CDN plus tard, et de verrouiller l'ingress des services.
#
# ─── Un seul hôte, routage par CHEMIN ────────────────────────────────────────
#
# Décision produit : tout passe par `clef.<domaine>`, et la racine offre les deux
# entrées. Il n'y a donc **aucune règle d'hôte** à écrire — un seul hôte, et le LB
# répartit selon le chemin :
#
#   /api/*          → clef-api        (toutes les routes métier)
#   /auth/*         → clef-api        (tout le parcours OAuth)
#   /admin/super/*  → clef-api        ⚠️ voir la collision ci-dessous
#   tout le reste   → clef-frontend   (les deux applications Angular et l'accueil)
#
# ⚠️ **La collision `/admin`.** `/admin/` est le préfixe de l'application Angular
# d'administration, servie par le frontend. Mais `/admin/super` est un ROUTER DU
# BACKEND (app/admin/super_admin_routes.py). Les règles de chemin d'un url map se
# résolvent par préfixe le plus long : `/admin/super/*` gagne donc sur le service par
# défaut, et `/admin/vehicles` continue d'aller au frontend. Les blocs `test` en fin
# de fichier verrouillent ce comportement — et c'est **GCP** qui les évalue à
# l'apply, pas nous.
#
# ─── Conséquence : le relais nginx devient inutile en production ──────────────
#
# `frontend/clef.conf.template` relaie lui aussi /api et /auth. Derrière ce LB, ces
# requêtes ne l'atteignent jamais : elles sont routées avant. Le relais reste utile
# pour un accès direct à l'URL run.app, et le jour où l'ingress sera verrouillé sur
# le LB, il deviendra du code mort — à retirer alors, pas avant.
#
# ─── Ressources globales et policy d'organisation ────────────────────────────
#
# L'adresse, la règle de transfert, l'url map, le proxy et le certificat sont des
# ressources **globales**. La policy `constraints/gcp.resourceLocations`, qui a déjà
# refusé `global` pour Secret Manager et `us` pour Cloud Build, ne s'y applique pas :
# « This constraint does not affect where global resources ... are created ». Seuls
# les NEG sont régionaux, en europe-west1.

# Tout ce fichier est conditionné à la présence d'un domaine : test et prod n'en ont
# pas encore, et un LB sans domaine ne sert à rien tout en coûtant une règle de
# transfert à l'heure.
locals {
  lb_active = var.public_domain == "" ? 0 : 1
}

# ─── Adresse IP publique ──────────────────────────────────────────────────────
# Statique, parce que c'est elle qui va dans le DNS. Une IP éphémère changerait au
# moindre remplacement de la règle de transfert, et le domaine cesserait de résoudre.
resource "google_compute_global_address" "clef" {
  count   = local.lb_active
  name    = "clef-${var.environment}-ip"
  project = var.project_id

  lifecycle {
    # L'IP est publiée dans le DNS de la Croix-Rouge : la perdre impose une
    # reconfiguration DNS et une réémission de certificat.
    prevent_destroy = true
  }

  depends_on = [google_project_service.apis]
}

# ─── NEG serverless, un par service ───────────────────────────────────────────
# Un NEG serverless ne porte pas de contrôle de santé : Cloud Run gère lui-même la
# disponibilité de ses révisions. C'est pourquoi les backend services ci-dessous
# n'ont aucun `health_checks`.
resource "google_compute_region_network_endpoint_group" "frontend" {
  count                 = local.lb_active
  name                  = "clef-${var.environment}-neg-frontend"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = var.frontend_service_name
  }

  depends_on = [google_project_service.apis]
}

resource "google_compute_region_network_endpoint_group" "api" {
  count                 = local.lb_active
  name                  = "clef-${var.environment}-neg-api"
  project               = var.project_id
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = var.service_name
  }

  depends_on = [google_project_service.apis]
}

# ─── Backend services ─────────────────────────────────────────────────────────
resource "google_compute_backend_service" "frontend" {
  count                 = local.lb_active
  name                  = "clef-${var.environment}-be-frontend"
  project               = var.project_id
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  # Les bundles Angular sont servis par nginx : 30 s suffisent largement.
  timeout_sec = 30

  backend {
    group = google_compute_region_network_endpoint_group.frontend[0].id
  }
}

resource "google_compute_backend_service" "api" {
  count                 = local.lb_active
  name                  = "clef-${var.environment}-be-api"
  project               = var.project_id
  protocol              = "HTTP"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  # ⚠️ Doit rester ≥ au `timeoutSeconds` du service Cloud Run (300 s), sinon le LB
  # coupe une requête que le service traite encore — un import CSV volumineux, par
  # exemple. Le client verrait un 502 sans rien dans les logs applicatifs.
  timeout_sec = 300

  backend {
    group = google_compute_region_network_endpoint_group.api[0].id
  }
}

# ─── Politique TLS ────────────────────────────────────────────────────────────
# C'est la raison d'être du LB ici : le mappage de domaine Cloud Run ne permet pas
# de refuser TLS 1.0 et 1.1.
resource "google_compute_ssl_policy" "clef" {
  count           = local.lb_active
  name            = "clef-${var.environment}-tls"
  project         = var.project_id
  profile         = "MODERN"
  min_tls_version = "TLS_1_2"
}

# ─── Certificat managé ────────────────────────────────────────────────────────
# ⚠️ Il ne se provisionne QUE lorsque le domaine résout déjà vers l'IP ci-dessus.
# L'ordre d'exploitation est donc : apply, puis DNS, puis attente. Un certificat qui
# reste en `FAILED_NOT_VISIBLE` signifie que le DNS ne pointe pas encore la bonne IP.
resource "google_compute_managed_ssl_certificate" "clef" {
  count   = local.lb_active
  name    = "clef-${var.environment}-cert"
  project = var.project_id

  managed {
    domains = [var.public_domain]
  }

  lifecycle {
    # Un certificat managé ne se modifie pas : changer de domaine impose un nouveau
    # certificat. `create_before_destroy` évite une coupure entre les deux.
    create_before_destroy = true
  }
}

# ─── Routage ──────────────────────────────────────────────────────────────────
resource "google_compute_url_map" "clef" {
  count           = local.lb_active
  name            = "clef-${var.environment}-urlmap"
  project         = var.project_id
  default_service = google_compute_backend_service.frontend[0].id

  host_rule {
    hosts        = [var.public_domain]
    path_matcher = "clef"
  }

  path_matcher {
    name = "clef"
    # Par défaut le frontend : l'accueil, /admin/*, /form/*, et tous les fichiers
    # statiques. C'est le cas majoritaire, donc le défaut.
    default_service = google_compute_backend_service.frontend[0].id

    # Les préfixes du backend. `/auth` compte autant que `/api` : c'est tout le
    # parcours OAuth (login, callback, me, logout), déclaré avec prefix="/auth"
    # dans app/auth/routes.py.
    path_rule {
      paths   = ["/api/*", "/auth/*"]
      service = google_compute_backend_service.api[0].id
    }

    # ⚠️ Préfixe plus long que celui de l'application admin : c'est ce qui fait
    # gagner cette règle sur le service par défaut, sans casser /admin/vehicles.
    path_rule {
      paths   = ["/admin/super/*"]
      service = google_compute_backend_service.api[0].id
    }
  }

  # ⚠️ Ces tests sont évalués par GCP À L'APPLY, pas par nous : un url map dont un
  # `test` échoue est refusé. C'est donc une vérification du routage exécutée par la
  # plateforme elle-même, et le seul garde-fou qui ne dépend pas de notre lecture.
  test {
    description = "l'accueil va au frontend"
    host        = var.public_domain
    path        = "/"
    service     = google_compute_backend_service.frontend[0].id
  }
  test {
    description = "l'application admin va au frontend"
    host        = var.public_domain
    path        = "/admin/vehicles"
    service     = google_compute_backend_service.frontend[0].id
  }
  test {
    description = "l'application terrain va au frontend"
    host        = var.public_domain
    path        = "/form/vehicle/abc123"
    service     = google_compute_backend_service.frontend[0].id
  }
  test {
    description = "les routes métier vont à l'API"
    host        = var.public_domain
    path        = "/api/vehicles/DT75"
    service     = google_compute_backend_service.api[0].id
  }
  test {
    description = "le parcours OAuth va à l'API"
    host        = var.public_domain
    path        = "/auth/callback"
    service     = google_compute_backend_service.api[0].id
  }
  test {
    description = "les routes super-admin vont à l'API, pas au frontend"
    host        = var.public_domain
    path        = "/admin/super/cache"
    service     = google_compute_backend_service.api[0].id
  }
}

# ─── Entrée HTTPS ─────────────────────────────────────────────────────────────
resource "google_compute_target_https_proxy" "clef" {
  count            = local.lb_active
  name             = "clef-${var.environment}-https-proxy"
  project          = var.project_id
  url_map          = google_compute_url_map.clef[0].id
  ssl_certificates = [google_compute_managed_ssl_certificate.clef[0].id]
  ssl_policy       = google_compute_ssl_policy.clef[0].id
}

resource "google_compute_global_forwarding_rule" "https" {
  count                 = local.lb_active
  name                  = "clef-${var.environment}-https"
  project               = var.project_id
  target                = google_compute_target_https_proxy.clef[0].id
  ip_address            = google_compute_global_address.clef[0].id
  port_range            = "443"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}

# ─── Entrée HTTP : redirection seule ──────────────────────────────────────────
# Aucun contenu n'est servi en clair. La redirection est permanente et conserve le
# chemin, pour que les URL des QR codes et des courriels fonctionnent même si
# quelqu'un les tape en http://.
resource "google_compute_url_map" "redirection_https" {
  count   = local.lb_active
  name    = "clef-${var.environment}-urlmap-redirect"
  project = var.project_id

  default_url_redirect {
    https_redirect         = true
    redirect_response_code = "MOVED_PERMANENTLY_DEFAULT"
    strip_query            = false
  }
}

resource "google_compute_target_http_proxy" "redirection" {
  count   = local.lb_active
  name    = "clef-${var.environment}-http-proxy"
  project = var.project_id
  url_map = google_compute_url_map.redirection_https[0].id
}

resource "google_compute_global_forwarding_rule" "http" {
  count                 = local.lb_active
  name                  = "clef-${var.environment}-http"
  project               = var.project_id
  target                = google_compute_target_http_proxy.redirection[0].id
  ip_address            = google_compute_global_address.clef[0].id
  port_range            = "80"
  load_balancing_scheme = "EXTERNAL_MANAGED"
}
