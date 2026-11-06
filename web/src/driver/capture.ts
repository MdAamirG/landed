// The capture pipeline: what happens to a photo on the phone, before any network is needed.
// It checks blur and brightness, then shrinks the photo and prints a strip below the receipt.

export const MAX_PHOTO_BYTES = 300_000; // The server refuses anything bigger.

// The sharpness check runs on a small copy: it is fast on a cheap phone, and tiny details such as
// paper grain stop counting as sharpness.
const SAMPLE_WIDTH_PX = 480;

// Starting values, set from the sample photos (blurry.jpg against the other four) and to be tuned
// on a real phone. Sending anyway after two failures means a bad value can't trap a driver.
const MIN_BRIGHTNESS = 60; // Mean grey level, 0 to 255.
const MIN_SHARPNESS = 30; // Variance of the Laplacian.

// Tried in order until the photo fits. Text on a receipt stays readable at 1600 px, so size only
// drops once quality has gone as far as it sensibly can.
const LONG_SIDES_PX = [1600, 1280, 1024, 800];
const JPEG_QUALITIES = [0.8, 0.65, 0.5, 0.4];

export type PhotoProblem = "blurred" | "dark";
export type DeviceCheck = "passed" | "sent_anyway";
export type GpsFix = { lat: number; lng: number; accuracyM: number };

export type PreparedPhoto = {
  blob: Blob;
  originalBytes: number;
  capturedAt: Date;
  gps: GpsFix | null;
  deviceCheck: DeviceCheck;
};

/** Mean brightness and sharpness from greyscale pixels. Pure, so it can be tested. */
export function measure(grey: ArrayLike<number>, width: number, height: number) {
  let total = 0;
  for (let i = 0; i < grey.length; i += 1) total += grey[i];
  const brightness = total / grey.length;

  // The Laplacian: how much each pixel differs from its four neighbours. A sharp photo has many
  // hard edges, so these values vary widely. A blurred one has soft edges and they stay small.
  let sum = 0;
  let sumOfSquares = 0;
  let count = 0;
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const at = y * width + x;
      const value =
        grey[at - width] + grey[at + width] + grey[at - 1] + grey[at + 1] - 4 * grey[at];
      sum += value;
      sumOfSquares += value * value;
      count += 1;
    }
  }
  const mean = sum / count;
  const sharpness = sumOfSquares / count - mean * mean;

  return { brightness, sharpness };
}

export function problemWith(photo: { brightness: number; sharpness: number }): PhotoProblem | null {
  if (photo.brightness < MIN_BRIGHTNESS) return "dark";
  if (photo.sharpness < MIN_SHARPNESS) return "blurred";
  return null;
}

/** Reads the file the camera gave us, turned the right way up. */
export function decodePhoto(file: Blob): Promise<ImageBitmap> {
  return createImageBitmap(file, { imageOrientation: "from-image" });
}

function drawingContext(width: number, height: number) {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", { willReadFrequently: true });
  if (!context) throw new Error("This phone can't draw to a canvas");
  return { canvas, context };
}

export function photoMeasurements(photo: ImageBitmap) {
  const width = Math.min(SAMPLE_WIDTH_PX, photo.width);
  const height = Math.round((photo.height / photo.width) * width);
  const { context } = drawingContext(width, height);
  context.drawImage(photo, 0, 0, width, height);

  const { data } = context.getImageData(0, 0, width, height); // Red, green, blue, alpha.
  const grey = new Uint8ClampedArray(width * height);
  for (let i = 0; i < grey.length; i += 1) {
    const at = i * 4;
    grey[i] = 0.299 * data[at] + 0.587 * data[at + 1] + 0.114 * data[at + 2]; // Perceived light.
  }
  return measure(grey, width, height);
}

function indiaTime(moment: Date): string {
  const time = new Intl.DateTimeFormat("en-IN", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone: "Asia/Kolkata",
  }).format(moment);
  return `${time} IST`;
}

/** The line printed below the receipt, so the proof stays with the image once it leaves the app. */
export function stripText(tripCode: string, capturedAt: Date, gps: GpsFix | null): string {
  const place = gps ? `${gps.lat.toFixed(5)}, ${gps.lng.toFixed(5)}` : "no location";
  return `${tripCode}   ${indiaTime(capturedAt)}   ${place}`;
}

function toJpeg(canvas: HTMLCanvasElement, quality: number): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => (blob ? resolve(blob) : reject(new Error("The photo couldn't be compressed"))),
      "image/jpeg",
      quality,
    );
  });
}

function drawWithStrip(photo: ImageBitmap, text: string, longSide: number): HTMLCanvasElement {
  const scale = Math.min(1, longSide / Math.max(photo.width, photo.height));
  const width = Math.round(photo.width * scale);
  const height = Math.round(photo.height * scale);
  const fontSize = Math.max(11, Math.min(22, Math.round((width / text.length) * 1.5)));
  const stripHeight = Math.round(fontSize * 2);

  const { canvas, context } = drawingContext(width, height + stripHeight);
  context.drawImage(photo, 0, 0, width, height);

  // Below the receipt, never over it. These are plain black and white because they are printed
  // into the image, which leaves the app, rather than being part of its interface.
  context.fillStyle = "#000";
  context.fillRect(0, height, width, stripHeight);
  context.fillStyle = "#fff";
  context.font = `${fontSize}px monospace`;
  context.textBaseline = "middle";
  context.fillText(text, fontSize, height + stripHeight / 2, width - fontSize * 2);
  return canvas;
}

/** The smallest change that fits: lower quality first, then fewer pixels. The strip is included. */
export async function compressWithStrip(photo: ImageBitmap, text: string): Promise<Blob> {
  for (const longSide of LONG_SIDES_PX) {
    const canvas = drawWithStrip(photo, text, longSide);
    for (const quality of JPEG_QUALITIES) {
      const blob = await toJpeg(canvas, quality);
      if (blob.size <= MAX_PHOTO_BYTES) return blob;
    }
  }
  throw new Error("The photo wouldn't fit under the size limit");
}
