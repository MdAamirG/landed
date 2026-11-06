import { describe, expect, it } from "vitest";

import { ApiError, type AttemptResult } from "../lib/api";
import type { PreparedPhoto } from "./capture";
import { createPhotoQueue, type PendingPhoto, type PhotoStore } from "./pendingPhotos";

const TRIP = "TRP-66134";

const CONFIRMED: AttemptResult = {
  attempt_id: "server-copy",
  attempt_no: 1,
  outcome: null,
  reason_codes: [],
  retakes_used: 0,
};

function fakeStore(): PhotoStore & { photos: Map<string, PendingPhoto> } {
  const photos = new Map<string, PendingPhoto>();
  return {
    photos,
    get: async (tripCode) => photos.get(tripCode),
    put: async (photo) => void photos.set(photo.tripCode, photo),
    remove: async (tripCode) => void photos.delete(tripCode),
  };
}

function shot(tripCode = TRIP, label = "first") {
  const prepared: PreparedPhoto = {
    blob: new Blob([label]),
    originalBytes: 3_000_000,
    capturedAt: new Date("2026-11-07T09:00:00Z"),
    gps: null,
    deviceCheck: "passed",
  };
  return { ...prepared, tripCode, token: "link-token" };
}

/** A network that plays back a list: an error to throw, or a confirmation. */
function fakeNetwork(...replies: (ApiError | "confirmed")[]) {
  const sent: PendingPhoto[] = [];
  const send = async (photo: PendingPhoto) => {
    sent.push(photo);
    const reply = replies.shift() ?? "confirmed";
    if (reply === "confirmed") return CONFIRMED;
    throw reply;
  };
  return { send, sent };
}

function ids() {
  let next = 0;
  return () => `attempt-${(next += 1)}`;
}

describe("the pending-photo queue", () => {
  it("holds a saved photo until it is sent", async () => {
    const store = fakeStore();
    const queue = createPhotoQueue(store, fakeNetwork().send, ids());

    const saved = await queue.save(shot());

    expect(saved.attemptId).toBe("attempt-1");
    expect(await queue.pending(TRIP)).toEqual(saved);
  });

  it("keeps one pending photo per trip, so a new shot replaces an unsent one", async () => {
    const store = fakeStore();
    const network = fakeNetwork();
    const queue = createPhotoQueue(store, network.send, ids());

    await queue.save(shot(TRIP, "first"));
    const second = await queue.save(shot(TRIP, "second"));
    await queue.trySend(TRIP);

    expect(network.sent).toHaveLength(1);
    expect(network.sent[0].attemptId).toBe(second.attemptId);
    expect(await network.sent[0].blob.text()).toBe("second");
  });

  it("forgets a discarded photo, leaving other trips' photos alone", async () => {
    const queue = createPhotoQueue(fakeStore(), fakeNetwork().send);
    await queue.save(shot());
    await queue.save(shot("TRP-66141"));

    await queue.discard(TRIP);

    expect(await queue.pending(TRIP)).toBeUndefined();
    expect(await queue.pending("TRP-66141")).toBeDefined();
  });

  it("keeps photos for different trips apart", async () => {
    const store = fakeStore();
    const queue = createPhotoQueue(store, fakeNetwork().send, ids());

    await queue.save(shot("TRP-1"));
    await queue.save(shot("TRP-2"));
    await queue.trySend("TRP-1");

    expect(await queue.pending("TRP-1")).toBeUndefined();
    expect(await queue.pending("TRP-2")).toBeDefined();
  });

  it("uses the same attempt ID on every retry", async () => {
    const offline = new ApiError(0);
    const network = fakeNetwork(offline, offline, offline, "confirmed");
    const queue = createPhotoQueue(fakeStore(), network.send, ids());
    await queue.save(shot());

    for (let tries = 0; tries < 4; tries += 1) await queue.trySend(TRIP);

    expect(network.sent).toHaveLength(4);
    expect(new Set(network.sent.map((photo) => photo.attemptId)).size).toBe(1);
  });

  it("keeps the photo after a failed send and records when it tried", async () => {
    const triedAt = new Date("2026-11-07T09:30:00Z");
    const store = fakeStore();
    const queue = createPhotoQueue(
      store,
      fakeNetwork(new ApiError(0)).send,
      ids(),
      () => triedAt,
    );
    await queue.save(shot());

    const outcome = await queue.trySend(TRIP);

    expect(outcome).toEqual({ status: "waiting" });
    expect((await queue.pending(TRIP))?.triedAt).toEqual(triedAt);
  });

  it("treats a server error as waiting, because it may pass", async () => {
    const queue = createPhotoQueue(fakeStore(), fakeNetwork(new ApiError(503)).send, ids());
    await queue.save(shot());

    expect(await queue.trySend(TRIP)).toEqual({ status: "waiting" });
    expect(await queue.pending(TRIP)).toBeDefined();
  });

  it("clears the photo only after the server confirms it", async () => {
    const store = fakeStore();
    const queue = createPhotoQueue(store, fakeNetwork("confirmed").send, ids());
    await queue.save(shot());

    const outcome = await queue.trySend(TRIP);

    expect(outcome).toEqual({ status: "sent", attempt: CONFIRMED });
    expect(await queue.pending(TRIP)).toBeUndefined();
  });

  it("keeps the photo when the link has expired, and says so", async () => {
    const queue = createPhotoQueue(fakeStore(), fakeNetwork(new ApiError(401)).send, ids());
    await queue.save(shot());

    expect(await queue.trySend(TRIP)).toEqual({ status: "link-dead" });
    expect(await queue.pending(TRIP)).toBeDefined();
  });

  it("keeps the photo when the server refuses it for another reason", async () => {
    const queue = createPhotoQueue(fakeStore(), fakeNetwork(new ApiError(429)).send, ids());
    await queue.save(shot());

    expect(await queue.trySend(TRIP)).toEqual({ status: "refused" });
    expect(await queue.pending(TRIP)).toBeDefined();
  });

  it("does not clear a newer photo when an older send is confirmed", async () => {
    const store = fakeStore();
    let replace = async () => {};
    const queue = createPhotoQueue(
      store,
      async () => {
        await replace(); // The driver takes a new shot while this send is on its way.
        return CONFIRMED;
      },
      ids(),
    );
    await queue.save(shot(TRIP, "first"));
    replace = async () => {
      await queue.save(shot(TRIP, "second"));
    };

    await queue.trySend(TRIP);

    const left = await queue.pending(TRIP);
    expect(left?.attemptId).toBe("attempt-2");
    expect(await left?.blob.text()).toBe("second");
  });

  it("does not bring back an older photo when its send fails", async () => {
    const store = fakeStore();
    let replace = async () => {};
    const queue = createPhotoQueue(
      store,
      async () => {
        await replace();
        throw new ApiError(0);
      },
      ids(),
    );
    await queue.save(shot(TRIP, "first"));
    replace = async () => {
      await queue.save(shot(TRIP, "second"));
    };

    await queue.trySend(TRIP);

    expect((await queue.pending(TRIP))?.attemptId).toBe("attempt-2");
  });

  it("does not start a second send while one is on its way", async () => {
    let finish = (_: AttemptResult) => {};
    let calls = 0;
    const queue = createPhotoQueue(
      fakeStore(),
      () => {
        calls += 1;
        return new Promise((resolve) => (finish = resolve));
      },
      ids(),
    );
    await queue.save(shot());

    const first = queue.trySend(TRIP);
    await new Promise((resolve) => setTimeout(resolve)); // Let the first send reach the network.
    const second = await queue.trySend(TRIP);
    finish(CONFIRMED);

    expect(second).toEqual({ status: "waiting" });
    expect((await first).status).toBe("sent");
    expect(calls).toBe(1);
  });

  it("has nothing to send when nothing is pending", async () => {
    const network = fakeNetwork();
    const queue = createPhotoQueue(fakeStore(), network.send, ids());

    expect(await queue.trySend(TRIP)).toEqual({ status: "nothing-pending" });
    expect(network.sent).toHaveLength(0);
  });
});
