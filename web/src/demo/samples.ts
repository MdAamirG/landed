// The sample photos, imported from samples/pods rather than copied, so there's one set of them.
// The build gives each a hashed file in /assets. Only the demo screens ever fetch them.

import blurry from "../../../samples/pods/photos/blurry.jpg";
import clean from "../../../samples/pods/photos/clean.jpg";
import noStamp from "../../../samples/pods/photos/no-stamp.jpg";
import short6Cartons from "../../../samples/pods/photos/short-6-cartons.jpg";
import wrongLr from "../../../samples/pods/photos/wrong-lr.jpg";

const SAMPLE_URLS: Record<string, string> = {
  clean,
  blurry,
  "no-stamp": noStamp,
  "short-6-cartons": short6Cartons,
  "wrong-lr": wrongLr,
};

/** The scenario's photo as a file, so it can go through the same steps as one from the camera. */
export async function samplePhoto(scenario: string): Promise<File> {
  const response = await fetch(SAMPLE_URLS[scenario]);
  if (!response.ok) throw new Error(`No sample photo for ${scenario}`);
  return new File([await response.blob()], `${scenario}.jpg`, { type: "image/jpeg" });
}
