import { Injectable, inject } from '@angular/core';
import { SwUpdate } from '@angular/service-worker';
import { fromEvent, merge, of } from 'rxjs';
import { map } from 'rxjs/operators';

/**
 * Service to handle PWA features for admin app
 */
@Injectable({
  providedIn: 'root'
})
export class PwaService {
  private readonly swUpdate = inject(SwUpdate);

  /**
   * Observable that emits true when online, false when offline
   */
  readonly online$ = merge(
    of(navigator.onLine),
    fromEvent(window, 'online').pipe(map(() => true)),
    fromEvent(window, 'offline').pipe(map(() => false))
  );

  constructor() {
    // Check for service worker updates
    if (this.swUpdate.isEnabled) {
      this.swUpdate.versionUpdates.subscribe(event => {
        if (event.type === 'VERSION_READY') {
          if (confirm('New version available. Load new version?')) {
            window.location.reload();
          }
        }
      });
    }
  }

  /**
   * Check if currently online
   */
  isOnline(): boolean {
    return navigator.onLine;
  }

  /**
   * Check for updates manually
   */
  async checkForUpdates(): Promise<boolean> {
    if (this.swUpdate.isEnabled) {
      return this.swUpdate.checkForUpdate();
    }
    return false;
  }

  /**
   * Activate the latest version
   */
  async activateUpdate(): Promise<void> {
    if (this.swUpdate.isEnabled) {
      await this.swUpdate.activateUpdate();
      window.location.reload();
    }
  }
}

