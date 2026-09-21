import '@testing-library/jest-dom/vitest';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';
// jsdom does not implement the browser's native modal dialog method.
Object.defineProperty(HTMLDialogElement.prototype, 'showModal', {
  configurable: true, writable: true,
  value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); },
});
Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
  configurable: true, writable: true, value: () => undefined,
});
afterEach(cleanup);
