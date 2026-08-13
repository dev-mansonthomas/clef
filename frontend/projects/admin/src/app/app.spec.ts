import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

/**
 * `App` est la racine : son gabarit ne contient qu'un `<router-outlet>`.
 *
 * Le test `should render title` généré par `ng new` attendait un `<h1>` contenant
 * « Hello, admin » — un reste de scaffold qui ne pouvait pas passer, et que
 * personne n'a vu échouer puisque `ng test` ne compilait pas (docs/TODO.md M4).
 */
describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [provideRouter([])],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(App);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should expose the application title', () => {
    const fixture = TestBed.createComponent(App);
    // `title` est `protected` : accès par indexation.
    expect(fixture.componentInstance['title']()).toBe('admin');
  });

  it('should render the router outlet', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('router-outlet')).not.toBeNull();
  });
});
