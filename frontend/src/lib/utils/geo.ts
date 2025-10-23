import { BBox } from '@turf/helpers';

/**
 * Unions any number of bounding boxes into a single bbox
 * @param bboxes array of boundign boxes Array<[minLon, minLat, maxLon, maxLat]>
 * @returns uni
 */
export const combineBoundingBoxes = (bboxes: BBox[]): BBox => {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (let i = 0; i < bboxes.length; i++) {
    const b = bboxes[i];
    if (b[0] < west) west = b[0];
    if (b[1] < south) south = b[1];
    if (b[2] > east) east = b[2];
    if (b[3] > north) north = b[3];
  }
  const bounds = [west, south, east, north] as BBox;
  if (bounds.includes(Infinity) || bounds.includes(-Infinity)) {
    return null;
  }
  return bounds;
};
