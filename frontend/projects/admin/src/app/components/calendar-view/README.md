# Calendar View Component

Vue calendrier en lecture seule pour les réservations de véhicules.

## Features

- **Vue hebdomadaire par défaut** : Affichage des réservations sur une semaine
- **Lecture seule** : Pas de drag & drop, pas de modification directe
- **Couleurs par véhicule** : Chaque véhicule a sa propre couleur
- **Format standardisé** : `{indicatif} - {chauffeur} - {mission}`
- **Navigation** : Boutons précédent/suivant pour naviguer entre les semaines
- **Auto-refresh** : Actualisation automatique toutes les 5 minutes
- **Responsive** : Adapté pour desktop
- **Locale française** : Jours et mois en français

## Usage

```typescript
import { CalendarViewComponent } from './components/calendar-view/calendar-view.component';

// In routes
{ path: 'calendar', component: CalendarViewComponent }
```

## Mock Data

Le composant utilise actuellement des données mockées pour le développement.
Les événements mockés incluent :
- VL75-01 - Jean Dupont - Mission Secours
- VL75-02 - Marie Martin - Transport Matériel
- VPSP75-01 - Pierre Durand - Maraude
- VL75-03 - Sophie Bernard - Formation
- VPSP75-02 - Luc Petit - Intervention Urgente

## Backend Integration

Lorsque l'endpoint `/api/calendar/events` sera disponible (task 2.4), mettre à jour la méthode `loadEvents()` :

1. Décommenter l'appel API
2. Supprimer les données mockées
3. S'assurer que l'API retourne le format attendu

### Format attendu de l'API

```json
[
  {
    "id": "event-123",
    "summary": "VL75-01 - Jean Dupont - Mission Secours",
    "start": {
      "dateTime": "2024-01-15T10:00:00",
      "timeZone": "Europe/Paris"
    },
    "end": {
      "dateTime": "2024-01-15T14:00:00",
      "timeZone": "Europe/Paris"
    },
    "colorId": "5"
  }
]
```

## Dependencies

- `@fullcalendar/core`
- `@fullcalendar/angular`
- `@fullcalendar/timegrid`
- `@fullcalendar/interaction`

## Configuration

Le calendrier est configuré avec :
- Plage horaire : 6h00 - 22h00
- Pas de slot "toute la journée"
- Hauteur automatique
- Locale : français
- Vue par défaut : semaine

