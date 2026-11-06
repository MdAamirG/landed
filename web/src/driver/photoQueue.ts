// The real queue: IndexedDB for storage and the API for the network. The logic itself is in
// pendingPhotos.ts. IndexedDB is the one browser store that holds image blobs and survives the
// browser closing.

import { uploadAttempt } from "../lib/api";
import { createPhotoQueue, type PendingPhoto, type PhotoStore } from "./pendingPhotos";

const DATABASE = "landed-driver";
const PHOTOS = "pending-photos";

function openDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const opening = indexedDB.open(DATABASE, 1);
    opening.onupgradeneeded = () => {
      opening.result.createObjectStore(PHOTOS, { keyPath: "tripCode" });
    };
    opening.onsuccess = () => resolve(opening.result);
    opening.onerror = () => reject(opening.error);
  });
}

/** Runs one request in its own transaction, and waits until that transaction is safely stored. */
async function withPhotos<T>(
  mode: IDBTransactionMode,
  run: (photos: IDBObjectStore) => IDBRequest<T>,
): Promise<T> {
  const database = await openDatabase();
  return new Promise((resolve, reject) => {
    const transaction = database.transaction(PHOTOS, mode);
    const request = run(transaction.objectStore(PHOTOS));
    transaction.oncomplete = () => {
      database.close();
      resolve(request.result);
    };
    transaction.onerror = () => {
      database.close();
      reject(transaction.error);
    };
  });
}

const indexedDbStore: PhotoStore = {
  get: (tripCode) => withPhotos<PendingPhoto | undefined>("readonly", (s) => s.get(tripCode)),
  put: async (photo) => {
    await withPhotos("readwrite", (photos) => photos.put(photo));
  },
  remove: async (tripCode) => {
    await withPhotos("readwrite", (photos) => photos.delete(tripCode));
  },
};

export const photoQueue = createPhotoQueue(indexedDbStore, (photo) =>
  uploadAttempt(photo.token, photo.attemptId, photo),
);
