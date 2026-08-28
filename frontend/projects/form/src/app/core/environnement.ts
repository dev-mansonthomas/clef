/**
 * Quel environnement sert cette page — déduit du NOM D'HÔTE.
 *
 * ⚠️ Pourquoi l'hôte, et pas une variable de build : une seule image de conteneur sert
 * dev, recette et production. Une valeur gravée à la construction imposerait une image
 * par environnement, et c'est justement ce que le déploiement évite. L'hôte, lui, EST
 * le marqueur : les environnements sont préfixés (`dev.clef.…`), le domaine nu est
 * réservé à la production.
 *
 * ⚠️ Pourquoi pas un appel à l'API : cette information doit s'afficher sur l'écran de
 * CONNEXION, donc avant toute session — et un point d'entrée public qui annonce
 * l'environnement est précisément ce qui a été retiré de `/api/test` (constat V9).
 *
 * ⚠️ Un hôte non reconnu n'est PAS supposé être la production : il est signalé comme
 * non identifié. Se croire en dev alors qu'on est en production est la seule erreur
 * qui coûte cher — les URL `*.run.app`, qui ne portent aucun marqueur, tombent ici.
 *
 * ⚠️ Ce fichier est DUPLIQUÉ dans les deux applications : ce workspace Angular n'a pas
 * de bibliothèque partagée, et en créer une pour trente lignes de table n'en vaut pas
 * le prix. Les deux copies doivent rester identiques — chaque application a son test.
 */
export type CodeEnvironnement = 'dev' | 'recette' | 'production' | 'inconnu';

export interface Environnement {
  code: CodeEnvironnement;
  /** Libellé affiché, en toutes lettres. Vide en production : rien à signaler. */
  libelle: string;
  /** Classe CSS portant la teinte de fond. */
  classe: string;
}

const PRODUCTION = ['clef.paquerette.com', 'clef.croix-rouge.fr'];

export function detecterEnvironnement(hostname: string): Environnement {
  const hote = (hostname || '').toLowerCase().replace(/^www\./, '');

  if (hote === 'localhost' || hote === '127.0.0.1' || hote.startsWith('dev.')) {
    return { code: 'dev', libelle: 'Développement', classe: 'env-dev' };
  }
  if (hote.startsWith('test.') || hote.startsWith('recette.')) {
    return { code: 'recette', libelle: 'Recette', classe: 'env-recette' };
  }
  if (PRODUCTION.includes(hote)) {
    return { code: 'production', libelle: '', classe: 'env-production' };
  }
  return {
    code: 'inconnu',
    libelle: 'Environnement non identifié',
    classe: 'env-inconnu'
  };
}

/** L'environnement de la page courante. */
export function environnementCourant(): Environnement {
  return detecterEnvironnement(
    typeof window === 'undefined' ? '' : window.location.hostname
  );
}
