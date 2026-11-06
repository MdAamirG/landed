// The pending-photo queue: the brief's hard part, with no UI in it. A photo goes in here before any
// attempt to send it, so a dead zone can't lose it. Storage and the network are passed in, which is
// what lets pendingPhotos.test.ts cover all of this without a browser.

import { ApiError, type AttemptResult } from "../lib/api";
import type { PreparedPhoto } from "./capture";

export type PendingPhoto = PreparedPhoto & {
  tripCode: string; // The key: one pending photo per trip.
  token: string; // Kept with the photo, because it decides who may send it.
  attemptId: string; // Made once, so every retry is the same attempt to the server.
  triedAt: Date | null;
};

export type PhotoStore = {
  get(tripCode: string): Promise<PendingPhoto | undefined>;
  put(photo: PendingPhoto): Promise<void>;
  remove(tripCode: string): Promise<void>;
};

export type SendOutcome =
  | { status: "sent"; attempt: AttemptResult }
  | { status: "nothing-pending" }
  | { status: "waiting" } // No network, or the server is down. Try again later.
  | { status: "link-dead" } // The photo stays on the phone, and the driver must call the office.
  | { status: "refused" }; // The server said no for another reason. The photo still stays.

export type PhotoQueue = {
  pending(tripCode: string): Promise<PendingPhoto | undefined>;
  save(photo: Omit<PendingPhoto, "attemptId" | "triedAt">): Promise<PendingPhoto>;
  trySend(tripCode: string): Promise<SendOutcome>;
  discard(tripCode: string): Promise<void>; // Only for a demo reset, which kills the photo's link.
};

function outcomeOf(error: unknown): SendOutcome {
  if (!(error instanceof ApiError) || error.status === 0 || error.status >= 500) {
    return { status: "waiting" };
  }
  return error.status === 401 ? { status: "link-dead" } : { status: "refused" };
}

export function createPhotoQueue(
  store: PhotoStore,
  send: (photo: PendingPhoto) => Promise<AttemptResult>,
  newAttemptId: () => string = () => crypto.randomUUID(),
  now: () => Date = () => new Date(),
): PhotoQueue {
  const sending = new Set<string>(); // The retry timer and the online event can fire together.

  /** True if this is still the photo waiting for the trip. A new shot may have replaced it. */
  async function stillPending(photo: PendingPhoto): Promise<boolean> {
    return (await store.get(photo.tripCode))?.attemptId === photo.attemptId;
  }

  return {
    pending: (tripCode) => store.get(tripCode),
    discard: (tripCode) => store.remove(tripCode),

    async save(photo) {
      // The store has one slot per trip, so this also replaces any unsent photo.
      const pending = { ...photo, attemptId: newAttemptId(), triedAt: null };
      await store.put(pending);
      return pending;
    },

    async trySend(tripCode) {
      const photo = await store.get(tripCode);
      if (!photo) return { status: "nothing-pending" };
      if (sending.has(tripCode)) return { status: "waiting" };

      sending.add(tripCode);
      try {
        const attempt = await send(photo);
        // Only the server's confirmation clears a photo, and only the photo it confirmed.
        if (await stillPending(photo)) await store.remove(tripCode);
        return { status: "sent", attempt };
      } catch (error) {
        if (await stillPending(photo)) await store.put({ ...photo, triedAt: now() });
        return outcomeOf(error);
      } finally {
        sending.delete(tripCode);
      }
    },
  };
}
