# Service Cloud Run du backend CLEF, avec Redis en sidecar.
#
# Appliqué par 01-gcp-deploy.sh via `gcloud run services replace`, après substitution
# des variables `${...}` par envsubst. Le format déclaratif est nécessaire : `gcloud run
# deploy` ne sait pas décrire plusieurs conteneurs ni un volume GCS.
#
# ─── Pourquoi Redis en sidecar ────────────────────────────────────────────────
# Cloud Run ne route que du HTTP/gRPC : un service ne peut pas exposer le port TCP de
# Redis. La seule topologie possible est donc deux conteneurs dans le MÊME service,
# communiquant par localhost.
#
# ⚠️ Conséquence : chaque instance a son propre Redis. Deux instances = deux jeux de
# données divergents, silencieusement. D'où maxScale=1, non négociable tant que Redis
# vit ici. Voir l'ADR 0008.
#
# ─── Durabilité ───────────────────────────────────────────────────────────────
# Instantané RDB toutes les 10 minutes sur un bucket GCS monté par Cloud Storage FUSE.
# Pas d'AOF : les appends sur un système de fichiers objet n'ont pas les garanties de
# fsync qu'exige un journal. RPO assumé : 10 minutes.
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: ${SERVICE_NAME}
  labels:
    app: clef
    environment: ${ENVIRONMENT}
spec:
  template:
    metadata:
      annotations:
        # Une seule instance : voir l'avertissement ci-dessus.
        autoscaling.knative.dev/maxScale: "${MAX_INSTANCES}"
        autoscaling.knative.dev/minScale: "${MIN_INSTANCES}"

        # gen2 est requis pour monter un volume GCS.
        run.googleapis.com/execution-environment: gen2

        # ⚠️ CPU allouée en permanence. Sans cela, Cloud Run bride le CPU entre deux
        # requêtes — et l'instantané périodique de Redis, qui est une tâche de fond,
        # ne s'exécuterait jamais. C'est le réglage sans lequel la durabilité annoncée
        # est fictive.
        run.googleapis.com/cpu-throttling: "false"

        run.googleapis.com/startup-cpu-boost: "true"

        # Ordre de démarrage : Redis d'abord. L'authentification lit le référentiel
        # dans Redis dès la première requête (tâche N2) ; un backend démarré avant sa
        # base répondrait 500 le temps que le sidecar monte.
        #
        # ⚠️ C'est une **annotation**, et non un champ `depends_on` sur le conteneur :
        # ce dernier est la syntaxe du provider Terraform, que l'API v1 utilisée par
        # `gcloud run services replace` ne connaît pas. L'y poser serait sans effet,
        # et sans erreur.
        #
        # Le `startupProbe` du conteneur redis n'est pas facultatif : c'est lui qui
        # permet à Cloud Run de constater que la dépendance est prête. Sans sonde,
        # l'annotation ne garantit rien.
        run.googleapis.com/container-dependencies: '{"backend":["redis"]}'
    spec:
      serviceAccountName: ${SERVICE_ACCOUNT}
      # ⚠️ Délai maximal d'une REQUÊTE, et rien d'autre.
      #
      # Le commentaire précédent affirmait que ce réglage laissait à Redis le temps
      # d'un dernier instantané sur SIGTERM, « bornant la perte bien en dessous des
      # 10 minutes ». C'est faux : dans l'API Knative utilisée ici,
      # `spec.template.spec.timeoutSeconds` est le délai de requête. Cloud Run
      # n'expose aucun délai de grâce à l'arrêt configurable.
      #
      # Le RPO réel à l'arrêt est donc la pleine fenêtre d'instantané, soit
      # 10 minutes. C'est ce que dit l'ADR 0008 ; ce commentaire prétendait le
      # contraire. 300 s reste utile en soi : un import CSV volumineux dépasse le
      # défaut de 60 s.
      timeoutSeconds: 300
      containers:
        # ─────────────────────────── Backend ───────────────────────────
        - name: backend
          image: ${BACKEND_IMAGE}
          ports:
            - name: http1
              containerPort: 8000
          env:
            - name: ENVIRONMENT
              value: ${ENVIRONMENT}
            - name: ENV
              value: ${ENVIRONMENT}
            # Le sidecar écoute sur localhost, dans le même espace réseau.
            - name: REDIS_URL
              value: redis://localhost:6379/0
            - name: GCP_PROJECT
              value: ${PROJECT_ID}
            # ⚠️ Volontairement ABSENT : USE_MOCKS. Son défaut est `false`, et
            # `assert_mocks_not_in_production()` refuse le démarrage si un mode mock
            # atteignait la production (constat S1).
            #
            # ⚠️ Volontairement ABSENT : GOOGLE_APPLICATION_CREDENTIALS. Le service
            # s'exécute SOUS le service account ci-dessus, sans clé (constat H6).
            - name: EMAIL_GESTIONNAIRE_DT
              value: ${EMAIL_GESTIONNAIRE_DT}
            # ⚠️ Le nom compte : `app/main.py` lit `CORS_ORIGINS`, et rien d'autre.
            # Une variable nommée autrement laisse le défaut en place —
            # « localhost:4200,localhost:4202,localhost:8000 ».
            #
            # Depuis que nginx relaie /api et /auth, frontend et backend sont la même
            # origine et CORS ne joue plus aucun rôle dans le parcours normal. On la
            # renseigne quand même : un accès direct au backend (Swagger, débogage)
            # passe par là.
            - name: CORS_ORIGINS
              value: ${CORS_ORIGINS}
            # ⚠️ NE PAS confondre avec CORS_ORIGINS, et surtout ne pas la retirer.
            #
            # `app/auth/config.py:65` la lit, et `app/auth/routes.py` s'en sert pour
            # VALIDER le paramètre `redirect_to` de /auth/login puis pour choisir la
            # destination après /auth/callback. Absente, le défaut est
            # « http://localhost:4200,http://localhost:4202 » : toute connexion
            # depuis le frontend déployé est rejetée en HTTP 400 « Invalid redirect
            # URL », et un callback réussi renvoie l'utilisateur sur localhost.
            #
            # Je l'avais supprimée en croyant le nom inventé — mon recoupement
            # cherchait `getenv("NOM"` sur une seule ligne, et l'appel est écrit sur
            # deux. Le test de garde ne voyait pas le trou : il vérifie que tout ce
            # qui est injecté est lu, pas que tout ce qui est lu est injecté.
            - name: ALLOWED_FRONTEND_URLS
              value: ${ALLOWED_FRONTEND_URLS}
            # Lue par `app/routers/dossiers_reparation.py` pour fabriquer le lien
            # d'approbation des devis envoyé aux garages. Défaut
            # « http://localhost:4200 » : des liens inutilisables dans des courriels
            # partis chez des tiers.
            - name: FRONTEND_URL
              value: ${FRONTEND_URL}
            # Lue par `app/services/qr_code_service.py:126`, qui construit
            # « https://${DOMAIN}/vehicle/<id> ». Défaut « clef.example.com ».
            #
            # ⚠️ C'est la variable la plus difficile à rattraper : ces URL sont
            # IMPRIMÉES et collées sur les véhicules. Une valeur fausse ne se corrige
            # pas par un redéploiement, elle se corrige au chiffon.
            - name: DOMAIN
              value: ${DOMAIN}
            # Le cookie de session est posé sur une origine HTTPS : il doit être
            # marqué Secure. Le défaut du code est `false`, pour le développement
            # local en HTTP clair.
            - name: SESSION_COOKIE_SECURE
              value: "true"
            - name: BACKEND_URL
              value: ${BACKEND_URL}
            # ⚠️ Sans cette variable, `app/auth/config.py` retombe sur
            # « http://localhost:8000/auth/callback » : Google renverrait chaque
            # utilisateur vers sa propre machine, et la connexion serait
            # intégralement cassée en production.
            #
            # ⚠️⚠️ Et elle doit pointer l'origine du **FRONTEND**, pas celle de
            # l'API. Le backend pose le cookie de session dans la réponse au
            # callback : le navigateur l'attribue à l'hôte qui lui a répondu. Sur
            # l'origine de l'API, le cookie serait posé pour `clef-api-*.run.app`,
            # puis le navigateur suivrait la redirection vers le frontend — dont les
            # appels ne porteraient aucun cookie. Connexion silencieusement cassée.
            #
            # nginx relaie déjà `/auth` : le callback traverse le proxy, le backend
            # répond, et le cookie est attribué à l'hôte du frontend. Tout reste en
            # même origine. C'est aussi cet URI, celui du frontend, qu'il faut
            # déclarer au client OAuth dans la console GCP.
            #
            # Vide au tout premier déploiement — l'URL du service n'existe pas
            # encore. 01-gcp-deploy.sh redéploie alors une seconde fois, une fois
            # l'URL connue.
            - name: GOOGLE_REDIRECT_URI
              value: ${GOOGLE_REDIRECT_URI}
            - name: VEHICULES_SPREADSHEET_ID
              value: ${VEHICULES_SPREADSHEET_ID}
            - name: BENEVOLES_SPREADSHEET_ID
              value: ${BENEVOLES_SPREADSHEET_ID}
            - name: RESPONSABLES_SPREADSHEET_ID
              value: ${RESPONSABLES_SPREADSHEET_ID}
            - name: GOOGLE_CLIENT_ID
              valueFrom:
                secretKeyRef:
                  # Ressource préfixée : projet partagé, espace de noms commun.
                  name: CLEF_GOOGLE_CLIENT_ID
                  key: latest
            - name: GOOGLE_CLIENT_SECRET
              valueFrom:
                secretKeyRef:
                  # Ressource préfixée : projet partagé, espace de noms commun.
                  name: CLEF_GOOGLE_CLIENT_SECRET
                  key: latest
            - name: QR_CODE_SALT
              valueFrom:
                secretKeyRef:
                  # Ressource préfixée : projet partagé, espace de noms commun.
                  name: CLEF_QR_CODE_SALT
                  key: latest
          resources:
            limits:
              cpu: "1"
              memory: 512Mi
          startupProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 5
            periodSeconds: 5
            failureThreshold: 12
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            periodSeconds: 30

        # ─────────────────────────── Redis ─────────────────────────────
        - name: redis
          image: redis:8.10
          # Configuration passée en arguments plutôt que par un fichier monté : cela
          # évite un second volume et rend le réglage lisible ici, à côté de son
          # explication.
          args:
            - redis-server
            # Instantané si au moins 1 clé a changé depuis 600 s. Deux fenêtres pour
            # que les rafales d'écritures soient capturées plus vite.
            - --save
            - "600 1"
            - --save
            - "120 100"
            # Pas d'AOF : les appends sur un système de fichiers objet n'offrent pas
            # les garanties de fsync qu'exige un journal.
            - --appendonly
            - "no"
            - --dir
            - /snapshots
            - --dbfilename
            - dump.rdb
            # Ne pas refuser les écritures si un instantané échoue : mieux vaut servir
            # avec un risque de perte que rendre l'application inutilisable. L'échec
            # reste visible dans les logs.
            - --stop-writes-on-bgsave-error
            - "no"
            # Redis est ici la base, pas un cache : ne jamais évincer de clé.
            #
            # ⚠️ `noeviction` seul ne protège de rien : sans `--maxmemory`, Redis
            # n'a aucune limite à comparer, et c'est Cloud Run qui tue le conteneur
            # en dépassement mémoire. L'instance redémarre alors sur le dernier
            # instantané — jusqu'à 10 minutes d'écritures perdues, sans qu'aucun
            # signal Redis ne l'explique.
            #
            # Avec une limite, Redis refuse l'écriture et le client reçoit une
            # erreur claire. La marge sous la limite du conteneur n'est pas du
            # confort : un BGSAVE duplique les pages modifiées pendant sa durée
            # (copy-on-write), et cette copie n'est pas comptée dans `maxmemory`.
            - --maxmemory
            - ${REDIS_MAXMEMORY}
            - --maxmemory-policy
            - noeviction
          # Requis par `container-dependencies` (voir l'annotation). Un sidecar ne
          # peut pas déclarer de `ports` — seul le conteneur d'entrée en a — mais la
          # sonde nomme son port elle-même.
          #
          # 30 × 2 s = 60 s au plus. Redis démarre en moins d'une seconde à vide ; la
          # marge couvre le chargement d'un dump.rdb depuis GCS FUSE, le cas lent.
          startupProbe:
            tcpSocket:
              port: 6379
            periodSeconds: 2
            timeoutSeconds: 2
            failureThreshold: 30
          volumeMounts:
            - name: snapshots
              mountPath: /snapshots
          resources:
            limits:
              cpu: "1"
              memory: ${REDIS_MEMORY}
      volumes:
        - name: snapshots
          csi:
            driver: gcsfuse.run.googleapis.com
            volumeAttributes:
              bucketName: ${SNAPSHOTS_BUCKET}
  traffic:
    - percent: 100
      latestRevision: true
