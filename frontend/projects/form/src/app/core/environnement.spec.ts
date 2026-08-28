import { detecterEnvironnement } from './environnement';

/**
 * La table des environnements est dupliquée dans les deux applications : chaque copie
 * a son test, et les deux doivent rester identiques.
 *
 * Le cas qui compte est le DERNIER : un hôte non reconnu ne doit jamais être présenté
 * comme la production ni comme dev. Se croire en dev alors qu'on est en production est
 * la seule erreur qui coûte cher — et les URL `*.run.app` ne portent aucun marqueur
 * d'environnement.
 */
describe('detecterEnvironnement', () => {
  it('reconnaît le développement au préfixe dev.', () => {
    const env = detecterEnvironnement('dev.clef.paquerette.com');
    expect(env.code).toBe('dev');
    expect(env.libelle).toBe('Développement');
    expect(env.classe).toBe('env-dev');
  });

  it('reconnaît le poste local', () => {
    expect(detecterEnvironnement('localhost').code).toBe('dev');
    expect(detecterEnvironnement('127.0.0.1').code).toBe('dev');
  });

  it('reconnaît la recette aux préfixes test. et recette.', () => {
    expect(detecterEnvironnement('test.clef.paquerette.com').libelle).toBe('Recette');
    expect(detecterEnvironnement('recette.clef.paquerette.com').classe).toBe('env-recette');
  });

  it('ne signale RIEN en production — le domaine nu', () => {
    const env = detecterEnvironnement('clef.paquerette.com');
    expect(env.code).toBe('production');
    expect(env.libelle).toBe('');
  });

  it('accepte le domaine Croix-Rouge comme production', () => {
    expect(detecterEnvironnement('clef.croix-rouge.fr').code).toBe('production');
  });

  it('est insensible à la casse et au www.', () => {
    expect(detecterEnvironnement('DEV.Clef.Paquerette.COM').code).toBe('dev');
    expect(detecterEnvironnement('www.clef.paquerette.com').code).toBe('production');
  });

  it('refuse de deviner sur un hôte inconnu, plutôt que de supposer la production', () => {
    const env = detecterEnvironnement('clef-frontend-p4x6pl7fiq-ew.a.run.app');
    expect(env.code).toBe('inconnu');
    expect(env.libelle).toBe('Environnement non identifié');
  });

  it('ne casse pas sur une valeur vide', () => {
    expect(detecterEnvironnement('').code).toBe('inconnu');
  });
});
