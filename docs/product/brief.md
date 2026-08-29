# Brief — Multi-délégation : supprimer `DT75` en dur et poser l'administration globale

> Issu d'un `/brainstorm` du 2026-08-29. **Ce document n'est pas une spec** : il cadre
> le besoin et nomme les décisions prises, pour qu'un `/spec` puisse s'écrire ensuite.
> Les faits sur le code existant ont été relevés par lecture, pas de mémoire.

## Problème

Le backend de CLEF est conçu multi-tenant — toute clé Redis est préfixée par le code de
délégation (`RedisService._key()`), et c'est le **seul** mécanisme d'isolation. Mais
`DT75` est écrit en dur à des endroits qui décident : deux chemins d'authentification
(`app/auth/service.py:52` et `:116`), l'amorçage du référentiel (`app/main.py:136`), et
**quatre services du frontend admin** qui ne consultent jamais l'utilisateur connecté
(`api-keys`, `stats`, `unite-locale`, `vehicle-import`), plus `vehicle-edit` qui injecte
`'DT75'` dans une liste d'options.

Conséquence : une seconde délégation ne verrait pas ses propres données, et rien ne le
signalerait — elle verrait celles de la DT75. La cible à terme est un multi-DT national ;
la demande immédiate est de **ne pas construire la dette maintenant**, en rendant l'UI et
l'API propres même sans seconde DT.

## Utilisateurs et cas d'usage principal

| Utilisateur | Cas d'usage | Fréquence |
|---|---|---|
| **Super admin** (une adresse, désignée par l'environnement) | ajouter une délégation : code DT + email de son gestionnaire | très rare — quelques fois par an |
| **Gestionnaire d'une nouvelle DT** | se connecter pour la première fois, configurer sa délégation, amorcer ses ressources Google | une fois par délégation |
| **Bénévole / gestionnaire existant** | ne rien voir changer | quotidien |

Le troisième est le plus important : ce chantier ne doit rien casser pour la DT75, qui
est la seule en service et porte 4546 bénévoles réels.

## Décisions prises pendant l'entretien

1. **Ambition : dette + socle maintenant, multi-DT national comme cible.** Pas de
   seconde délégation à court terme, mais l'UI et l'API doivent être propres pour ne pas
   payer deux fois.
2. **Un code DT est validé** : `^DT[A-Z0-9]+$`, dérivé du `Libelle_court` du
   référentiel national — majuscules, sans espace ni accent.

   ⚠️ J'avais proposé `^DT[0-9]{2,3}[AB]?$`. **Le fichier réel le réfute** : sur les
   108 entités départementales, **14 n'ont pas de code numérique** — `DT MARTINIQUE`,
   `DT REUNION`, `DT NOUVELLECALEDONIE`, `DT STPIERREMIQUELON`… et même `DT 2A` /
   `DT 2B`, que mon motif rejetait aussi. La normalisation du libellé court donne
   **108 codes distincts sur 108**, tous conformes à `^DT[A-Z0-9]+$`.

   Et le point qui décide : `Libelle_court` de la structure 80 vaut `'DT 75'`, donc le
   code produit est exactement **`DT75`** — celui que CLEF utilise déjà. L'import
   n'impose aucune migration des 4546 bénévoles existants.
3. **Le super admin est désigné par l'environnement**, et ne s'attribue pas depuis
   l'interface. ⚠️ `SUPER_ADMIN_EMAIL` n'est aujourd'hui injecté dans **aucun**
   environnement déployé : personne n'est super admin, et `/admin/super/*` est
   inaccessible à quiconque. À corriger dans ce chantier, sinon le menu global est
   inatteignable.
4. **L'application d'administration n'est ouverte qu'au gestionnaire DT et aux
   responsables véhicules.** Tout autre `@croix-rouge.fr` est refusé, avec un message
   expliquant d'attendre la synchronisation.

   ⚠️ **Changement de comportement** : aujourd'hui n'importe quelle adresse du domaine
   entre comme « Bénévole » rattachée à DT75 en dur. Trois exceptions nécessaires, sinon
   plus personne ne peut amorcer une délégation : l'adresse du super admin, l'email
   déclaré gestionnaire d'une DT, et les responsables véhicules — d'où la clé API
   « responsables » et son endpoint, qui existent déjà.

   L'application **terrain** (`form`) est un sujet distinct, traité plus tard : elle
   s'appuie sur le référentiel bénévoles et UL, et sa règle de périmètre est une
   recherche, pas un refus (voir ci-dessous).
5. **Les ressources Google d'une nouvelle DT sont créées par un Apps Script
   d'amorçage**, exécuté sous l'identité du gestionnaire, qui crée le dossier Drive et
   les classeurs puis déclare les URL à l'API. C'est la seule voie disponible : le
   service account **ne peut pas** créer de document dans ce Workspace (constat N13,
   structurel — le domaine interdit le partage vers une adresse
   `.gserviceaccount.com`).

## Le registre des structures

La création d'une délégation dispose de toutes les informations nécessaires — code,
`id_structure`, libellé, email du gestionnaire — et écrit donc la structure de données
au moment où elle a lieu. Il n'y a rien à deviner à la connexion : les index sont
écrits à la création.

**Un registre global, hors préfixe de délégation** : l'ensemble des codes, un document
par délégation, et un index par email de gestionnaire lu à la connexion.

⚠️ Ce sont les **premières clés Redis non préfixées par une délégation**. L'invariant
« le code DT est le premier segment de toute clé » — seul mécanisme d'isolation, appliqué
par l'application et non par le datastore — gagne une exception. Elle doit être écrite,
testée, et **bornée** à ce registre. Un balayage des délégations à chaque connexion
éviterait l'exception, mais tiendrait à 3 délégations et pas à 108 : c'est la cible qui
tranche.

### L'identifiant de structure Croix-Rouge

Toute entité porte un **`id_structure`** — l'identifiant interne Croix-Rouge — et un
**rattachement** vers sa structure parente. La délégation de Paris a l'`id_structure`
**80**, valeur qui figure déjà dans la configuration (`SUPER_ADMIN_DT_NUMERIC_ID`).

Pour une délégation, le rattachement vaut `1 - INSTANCES NATIONALES` : il n'est pas
exploité. Pour une UL, il **désigne sa délégation**, sous la forme
`{id_structure} - {libellé}` — c'est le lien parent/enfant du référentiel.

Le modèle de délégation et d'UL doit donc porter : `code`, `id_structure`, `libellé`,
`libellé court`, `type de structure`, et pour une UL l'`id_structure` de sa délégation.

⚠️ **`DD` et `DT` désignent la MÊME chose** : les délégations départementales ont été
renommées délégations territoriales, et le référentiel porte les deux libellés parce que
le renommage n'y est pas terminé — 72 `DELEGATION DEPARTEMENTALE - DD` contre 36
`DELEGATION TERRITORIALE - DT`. Paris (structure 80) est encore étiquetée `DD`. Même
histoire un niveau plus bas : les unités locales s'appelaient **délégations locales (DL)**.

Conséquence pratique : `Type_structure` ne doit **jamais** conditionner un traitement.
Filtrer sur `== 'DT'` perdrait les deux tiers des délégations, dont Paris. Une seule
notion dans CLEF — la délégation — et une seule pour l'échelon inférieur, l'unité
locale.

## Initialisation depuis le référentiel national

Le dossier `init_data/` (gitignoré) porte `DTUL.csv`, export du référentiel des
structures : **684 lignes — 108 délégations et 576 unités locales**, séparateur `;`.

Une **option de déploiement** doit initialiser toutes les délégations et leurs UL
rattachées, en rapportant les erreurs rencontrées ligne par ligne — même forme de compte
rendu que la synchronisation des bénévoles : une raison constante, les données en
colonnes.

**Le drapeau « cette délégation utilise CLEF »** décide de l'écrasement :

| État de la délégation | Comportement de l'import |
|---|---|
| **utilise CLEF** | les données ne sont **pas** écrasées — l'import signale les écarts et n'écrit rien |
| **n'utilise pas CLEF** | les données sont écrasées par le référentiel |

C'est ce qui permet de rejouer l'import quand les structures bougent — elles bougent
lentement, mais elles bougent — sans jamais écraser une délégation en service. La DT75,
seule en service, est donc protégée par construction dès que son drapeau est posé.

⚠️ Ce que le fichier valide déjà, vérifié par lecture : **0 rattachement mal formé**,
**0 UL orpheline** (toutes pointent une délégation présente dans le fichier), **108 codes
distincts sur 108**.

### La jointure des UL : résolue par l'`id_structure`

Le point fragile était le lien entre une UL du référentiel et l'UL telle que la nomme la
feuille des bénévoles : celle-ci donne `UNITE LOCALE DE PARIS XII`, soit le **`Libelle`**
du référentiel et non son libellé court (`UL PARIS12`). Une jointure sur du texte libre,
donc — le mode de panne déjà rencontré sur les en-têtes de colonnes.

**L'`id_structure` sera ajouté à l'export des bénévoles**, ce qui rend la jointure
stricte. Le point d'entrée de synchronisation l'accepte **déjà** (fait le 2026-08-29) :

- colonne **facultative** — 4546 lignes sont en service, l'exiger les ferait toutes
  échouer pour une donnée dont rien ne dépend encore ;
- **deux libellés acceptés**, `Id_structure` et `N_structure` : les deux exports du même
  référentiel national ne la nomment pas pareil, et deviner lequel arrivera aurait coûté
  une synchronisation en échec ;
- normalisée comme les autres champs : cellule numérique, espaces, cellule vide.

Il reste à écrire la jointure elle-même — l'`id_structure` est porté et stocké, il n'est
pas encore exploité.

## Objectifs

- Aucune occurrence de `DT75` dans le code de production, hors valeur par défaut de
  configuration, mocks et tests. **Vérifié par un test structurel**, pas par relecture.
- La délégation vient **toujours** de l'utilisateur authentifié, côté backend comme
  côté frontend.
- `DEFAULT_DT` (le réglage existe déjà, `app/auth/config.py`) sert d'amorçage, jamais de
  repli silencieux dans un chemin de données.
- Un super admin peut créer une délégation depuis un menu d'administration globale : code
  DT validé, email du gestionnaire, configuration initiale.
- Un Apps Script d'amorçage crée les ressources Google d'une nouvelle DT et déclare ses
  URL.
- Les délégations et UL portent leur **`id_structure`** et leur rattachement, et une
  option de déploiement les initialise depuis le référentiel national, sans jamais
  écraser une délégation qui utilise CLEF.
- Le parcours de la DT75 est inchangé — aucune régression pour la seule délégation en
  service.

## Non-objectifs

- Un utilisateur appartenant à **plusieurs** délégations : pas de sélecteur, pas de
  bascule en cours de session.
- L'inter-délégation dans son ensemble — **lecture comme écriture** — est hors périmètre
  de ce chantier. Mais il ne doit pas être rendu impossible : voir ci-dessous, et U1/U2
  dans `docs/TODO.md`.
- Migration ou **renommage** d'une délégation existante.
- **Suppression** d'une délégation — cela toucherait des données qui n'existent nulle
  part ailleurs.
- Échelle nationale : le dimensionnement Redis, les sauvegardes par DT et l'exploitation
  de N délégations restent hors périmètre. Seule contrainte retenue : ne pas rendre ces
  sujets plus coûteux qu'ils ne le sont.

### Le périmètre de recherche de l'application terrain (plus tard, mais il change une règle)

Un bénévole cherche par défaut les véhicules **de son UL**, et peut élargir : les autres
UL de son département, les véhicules **de la DT** elle-même, puis — cas du **renfort** —
les mêmes recherches **dans une autre délégation**.

⚠️ **Et cela va jusqu'à l'écriture.** J'avais écrit « aucune écriture croisée » comme
règle de repli : c'est faux aussi. Un bénévole de la DT75 qui réserve un véhicule de la
DT92 **matérialise la réservation dans la DT92**, à l'initiative de quelqu'un qui n'en
fait pas partie. La réservation référence alors une identité hors du périmètre où elle
est écrite.

La règle qui tient n'est donc ni « pas de lecture » ni « pas d'écriture », mais :
**rien d'implicite**. L'élargissement est un geste explicite de l'utilisateur, jamais un
défaut — une recherche qui ratisserait toutes les délégations ferait fuiter la flotte de
chacune à tout le monde. Le préfixe de délégation reste le mécanisme d'isolation, mais il
lui faut des **points de passage nommés et tracés**, pas des exceptions ajoutées au coup
par coup. Détail dans `docs/TODO.md`, U2.

### Cas d'usage à traiter séparément

**Un véhicule vendu à une autre délégation.** C'est un transfert inter-DT, donc
exactement ce que le cloisonnement interdit. Il demandera sa propre décision — que
devient l'historique du véhicule, ses dossiers de réparation, ses photos ? À inscrire au
`docs/TODO.md` comme cas d'usage, pas à traiter ici.

## Contraintes

- **Stack** : FastAPI + Pydantic v2, Redis 8 (JSON, Search), Angular 21 standalone. Rien
  de neuf à introduire.
- **Données** : l'isolation est **applicative**, pas garantie par le datastore. Toute
  route qui prend un `dt` en paramètre d'URL plutôt que dans la session est une faille de
  la classe **C3** — trois routers sont déjà dans ce cas, et ce chantier ne doit pas en
  ajouter.
- **Sécurité** : le périmètre se lit dans `current_user.dt`, jamais dans l'URL. Le refus
  d'un utilisateur inconnu ferme une porte aujourd'hui ouverte : à vérifier en exécution
  sur un compte réel avant de déployer.
- **Google Workspace** : le service account ne peut ni créer ni lire un document du
  domaine (N13). Toute automatisation passe par un Apps Script exécuté sous l'identité
  d'un humain.
- **Compatibilité** : la DT75 est en service avec 4546 bénévoles. Aucune migration de
  données n'est prévue ; les clés existantes restent valides.

## Risques et questions ouvertes

| Risque | Pourquoi c'est le plus dangereux |
|---|---|
| **Le refus des inconnus bloque un usage réel** | Aujourd'hui n'importe quel `@croix-rouge.fr` entre. Si des bénévoles se connectent avant d'être au référentiel, le refus les enferme dehors — et le message d'attente devient la seule explication. À éprouver avant de déployer. |
| **L'exception à l'invariant d'isolation** | Trois clés hors préfixe de DT, sur le chemin d'authentification. Une erreur là a une portée inter-délégation, ce que rien d'autre dans le système ne permet. |
| **Le frontend décide encore de la DT à quatre endroits** | Les corriger sans filet ferait passer une régression pour une correction. Un test structurel interdisant le littéral doit précéder les corrections. |
| **`SUPER_ADMIN_*` absent des environnements déployés** | Le menu global serait développé, déployé, et inaccessible — y compris à son auteur. |
| **La jointure UL référentiel ↔ feuille des bénévoles** | Elle se fait sur un libellé libre (`UNITE LOCALE DE PARIS XII`). Une variante d'orthographe et un bénévole se retrouve sans UL connue, donc sans périmètre — le même mode de panne que l'accent décomposé du référentiel bénévoles. |

Questions encore ouvertes :

- Le registre global : index inverse ou balayage ? (proposition ci-dessus, à confirmer)
- La création d'une DT écrit-elle une configuration initiale complète, ou seulement le
  strict nécessaire pour que le gestionnaire se connecte ?
- L'Apps Script d'amorçage : un quatrième script à installer par le gestionnaire, ou une
  extension du menu des scripts existants ?

## Première tranche

**Faire venir la délégation de l'utilisateur authentifié, partout — sans nouvelle
interface.**

1. Un **test structurel** qui échoue sur tout littéral `DT75` hors configuration, mocks
   et tests. Écrit d'abord : c'est lui qui rend les corrections vérifiables.
2. Backend : `auth/service.py:52` et `:116`, `main.py:136` passent par `DEFAULT_DT`
   comme valeur d'**amorçage** explicite, jamais comme repli de chemin de données.
3. Frontend : les quatre services et `vehicle-edit` lisent
   `authService.currentUserValue?.dt`. Les trois replis `?? 'DT75'` disparaissent — un
   utilisateur sans délégation est une anomalie, pas un cas à masquer.
4. `SUPER_ADMIN_EMAIL`, `SUPER_ADMIN_DT_ID` et `SUPER_ADMIN_DT_NUMERIC_ID` injectés par
   le gabarit Cloud Run et documentés dans `deploy/deploy.env.example`.

Cette tranche ne change **aucun comportement visible** pour la DT75 : elle rend seulement
possible la suivante. Le refus des inconnus, le registre global et le menu
d'administration viennent après, chacun avec sa propre spec.

## Suite

1. `/skills-review` — vérifier que les skills du projet couvrent ce chantier (rien de
   nouveau côté GCP a priori ; `redis-core` pour le modelage du registre global).
2. `/spec` sur la **première tranche** ci-dessus, pas sur le chantier entier.
3. Inscrire au `docs/TODO.md` deux cas d'usage : « véhicule vendu à une autre DT » et
   « recherche de véhicules inter-DT pour un renfort ».
4. L'import du référentiel des structures mérite **sa propre spec**, distincte du
   nettoyage `DT75` : il touche des données en service et son comportement dépend d'un
   drapeau par délégation.
