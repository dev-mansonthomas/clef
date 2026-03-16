import { Injectable, inject } from '@angular/core';
import { SwUpdate } from '@angular/service-worker';
import { fromEvent, merge, of } from 'rxjs';
import { map } from 'rxjs/operators';

/**
 * Service to handle offline form submissions and background sync
 */
@Injectable({
  providedIn: 'root'
})
export class OfflineSyncService {
  private readonly swUpdate = inject(SwUpdate);
  private readonly QUEUE_KEY = 'offline-form-queue';

  /**
   * Observable that emits true when online, false when offline
   */
  readonly online$ = merge(
    of(navigator.onLine),
    fromEvent(window, 'online').pipe(map(() => true)),
    fromEvent(window, 'offline').pipe(map(() => false))
  );

  constructor() {
    // Listen for online events to sync queued submissions
    this.online$.subscribe(isOnline => {
      if (isOnline) {
        this.syncQueuedSubmissions();
      }
    });

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
   * Queue a form submission for later sync when offline
   */
  queueSubmission(data: any): void {
    const queue = this.getQueue();
    queue.push({
      data,
      timestamp: new Date().toISOString(),
      id: crypto.randomUUID()
    });
    localStorage.setItem(this.QUEUE_KEY, JSON.stringify(queue));
  }

  /**
   * Get all queued submissions
   */
  getQueue(): any[] {
    const queueStr = localStorage.getItem(this.QUEUE_KEY);
    return queueStr ? JSON.parse(queueStr) : [];
  }

  /**
   * Clear the queue
   */
  clearQueue(): void {
    localStorage.removeItem(this.QUEUE_KEY);
  }

  /**
   * Sync all queued submissions when back online
   */
  private async syncQueuedSubmissions(): Promise<void> {
    const queue = this.getQueue();
    if (queue.length === 0) return;

    console.log(`Syncing ${queue.length} queued submissions...`);

    // Process each queued submission
    const results = await Promise.allSettled(
      queue.map(item => this.submitToServer(item.data))
    );

    // Remove successfully synced items
    const failedItems = queue.filter((_, index) => 
      results[index].status === 'rejected'
    );

    if (failedItems.length === 0) {
      this.clearQueue();
      console.log('All submissions synced successfully');
    } else {
      localStorage.setItem(this.QUEUE_KEY, JSON.stringify(failedItems));
      console.warn(`${failedItems.length} submissions failed to sync`);
    }
  }

  /**
   * Submit data to server
   */
  private async submitToServer(data: any): Promise<any> {
    // This should use the actual submission service
    // For now, just a placeholder
    const response = await fetch('/api/submissions', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  /**
   * Check if currently online
   */
  isOnline(): boolean {
    return navigator.onLine;
  }

  /**
   * Get count of queued submissions
   */
  getQueueCount(): number {
    return this.getQueue().length;
  }
}

