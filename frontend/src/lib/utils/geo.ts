import { BBox } from '@turf/helpers';
import { GeoJSONObject, Geometries } from '@turf/turf';
import type { Feature, FeatureCollection, Polygon } from 'geojson';

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

/**
 * Checks whether a GeoJSON object is a FeatureCollection.
 * @param geoJSON GeoJSON object to validate
 * @returns true when the object is a FeatureCollection
 */
export const isFeatureCollection = (
  geoJSON: GeoJSONObject
): geoJSON is FeatureCollection<Geometries, unknown> => geoJSON.type === 'FeatureCollection';

/**
 * Checks whether a GeoJSON object is a Feature.
 * @param geoJSON GeoJSON object to validate
 * @returns true when the object is a Feature
 */
export const isFeature = (geoJSON: GeoJSONObject): geoJSON is Feature<Geometries, unknown> =>
  geoJSON.type === 'Feature';

/**
 * Checks whether a coordinate position is valid.
 * @param position coordinate position candidate
 * @returns true when the value is an array of finite numeric coordinates
 */
export const isValidPosition = (position: unknown): position is number[] =>
  Array.isArray(position) && position.length >= 2 && position.every(Number.isFinite);

/**
 * Checks whether a ring is closed and valid for polygon geometry.
 * @param ring coordinate ring to validate
 * @returns true when the ring has at least four positions and starts/ends at the same point
 */
export const isClosedRing = (ring: number[][]): boolean => {
  if (ring.length < 4) return false;

  const firstPosition = ring[0];
  const lastPosition = ring[ring.length - 1];

  if (firstPosition.length !== lastPosition.length) return false;

  return firstPosition.every((value, index) => value === lastPosition[index]);
};

/**
 * Checks whether a value is a valid GeoJSON linear ring.
 * @param ring ring candidate
 * @returns true when the ring contains valid positions and is closed
 */
const isValidLinearRing = (ring: unknown): ring is number[][] =>
  Array.isArray(ring) && ring.every(isValidPosition) && isClosedRing(ring);

/**
 * Checks whether polygon coordinates are structurally valid.
 * @param coordinates polygon coordinates candidate
 * @returns true when all rings are valid linear rings
 */
export const isStructurallyValidPolygonCoordinates = (
  coordinates: unknown
): coordinates is Polygon['coordinates'] =>
  Array.isArray(coordinates) && coordinates.length > 0 && coordinates.every(isValidLinearRing);
