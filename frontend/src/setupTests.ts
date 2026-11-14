import '@testing-library/jest-dom';

if (typeof window !== 'undefined' && (typeof window.localStorage === 'undefined' || typeof window.localStorage.clear !== 'function')) {
  const store = new Map<string, string>();
  const storageMock: Storage = {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.get(key) ?? null;
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(window, 'localStorage', { value: storageMock, writable: true, configurable: true });
  Object.defineProperty(globalThis, 'localStorage', { value: storageMock, writable: true, configurable: true });
}

