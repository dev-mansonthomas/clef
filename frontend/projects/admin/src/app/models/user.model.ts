/**
 * User model matching backend auth
 */

export interface User {
  email: string;
  nom: string;
  prenom: string;
  dt: string;
  ul: string;
  role: string;
  perimetre: string;
  type_perimetre: string;
  is_super_admin?: boolean;
}

