import { selectLoader, load, parse } from '@loaders.gl/core';
import { KMLLoader } from '@loaders.gl/kml';
import { Loader } from '@loaders.gl/loader-utils';
import { ShapefileLoader } from '@loaders.gl/shapefile';
import { ZipLoader } from '@loaders.gl/zip';
import { featureCollection, GeoJSONObject, MultiPolygon } from '@turf/turf';
import type { Feature, FeatureCollection, Geometry, Position } from 'geojson';
import proj4 from 'proj4';

import {
  isFeature,
  isFeatureCollection,
  isStructurallyValidPolygonCoordinates,
} from '@/lib/utils/geo';

export enum UploadErrorType {
  Generic,
  InvalidXMLSyntax,
  SHPMissingFile,
  SHPMissingPRJ,
  UnsupportedFile,
  UnsupportedCRS,
  NoPolygons,
}

export const supportedFileformats = [
  ...KMLLoader.extensions,
  ...['kmz'],
  ...['shp', 'prj', 'shx', 'dbf', 'cfg'],
  ...['geojson'],
];

/**
 * Return the text content of a file
 * @param file File to read as text
 * @returns Text content of the file
 */
const readFileAsText = (file: File | ArrayBuffer): Promise<string> => {
  if (file instanceof ArrayBuffer) {
    return Promise.resolve(new TextDecoder().decode(file));
  }

  return new Promise((resolve, reject) => {
    const reader = new FileReader();

    reader.onload = (e) => {
      resolve(e.target.result as string);
    };

    reader.onerror = (e) => {
      reject(e);
    };

    reader.readAsText(file);
  });
};

/**
 * Validate a file and return an error message if it fails
 * @param file File to validate
 * @param loader Loader used to parse the file
 * @param intl Intl object for internationalization
 * @returns Error code if the validation fails
 */
export const validateFile = async (
  file: File | ArrayBuffer,
  loader: Loader
): Promise<UploadErrorType | undefined> => {
  switch (loader) {
    case KMLLoader: {
      // For the KML files, we're checking whether they are valid XML files. For this, we verify:
      // 1. that we can parse them with `DOMParser`
      // 2. that they don't contain parse errors using the technique described in
      //    https://stackoverflow.com/a/20294226
      try {
        const xml = new DOMParser().parseFromString(await readFileAsText(file), 'text/xml');

        const xmlWithError = new DOMParser().parseFromString('invalid', 'text/xml');

        const parseErrorNS = xmlWithError.getElementsByTagName('parsererror')[0].namespaceURI;

        if (xml.getElementsByTagNameNS(parseErrorNS, 'parsererror').length > 0) {
          return UploadErrorType.InvalidXMLSyntax;
        }
      } catch (e) {
        return UploadErrorType.Generic;
      }
      return;
    }

    default:
      return;
  }
};

/** Legacy CRS property found in pre-RFC 7946 GeoJSON files */
type LegacyCrs = {
  type?: string;
  properties?: { name?: string; code?: string | number };
};

type GeoJSONWithCrs = GeoJSONObject & { crs?: LegacyCrs };

/**
 * Extract an EPSG code from a legacy GeoJSON `crs` property.
 * Returns null if no crs is defined or if it's already WGS84 (4326).
 */
function extractNonWgs84Epsg(geojson: GeoJSONWithCrs): string | null {
  const { crs } = geojson;
  if (!crs?.properties) return null;

  let code: number | null = null;

  if (crs.type === 'name' && typeof crs.properties.name === 'string') {
    // Formats: "urn:ogc:def:crs:EPSG::3857", "EPSG:3857"
    const match = crs.properties.name.match(/EPSG:+(\d+)/i);
    if (match) code = parseInt(match[1], 10);
  } else if (typeof crs.properties.code === 'number') {
    code = crs.properties.code;
  } else if (typeof crs.properties.code === 'string') {
    code = parseInt(crs.properties.code, 10);
  }

  if (!code || code === 4326) return null;
  return `EPSG:${code}`;
}

function reprojectPosition(pos: Position, transformer: proj4.Converter): Position {
  const [x, y, ...rest] = pos;
  const [lon, lat] = transformer.forward([x, y]);
  return [lon, lat, ...rest];
}

function reprojectCoordinates(coords: unknown, transformer: proj4.Converter): unknown {
  if (!Array.isArray(coords)) return coords;
  // A position is an array of numbers
  if (typeof coords[0] === 'number') {
    return reprojectPosition(coords as Position, transformer);
  }
  return coords.map((coord) => reprojectCoordinates(coord, transformer));
}

function reprojectGeometry(geometry: Geometry, transformer: proj4.Converter): Geometry {
  if (geometry.type === 'GeometryCollection') {
    return {
      ...geometry,
      geometries: geometry.geometries.map((g) => reprojectGeometry(g as Geometry, transformer)),
    };
  }
  const geo = geometry as Exclude<Geometry, GeoJSON.GeometryCollection>;
  return {
    ...geo,
    coordinates: reprojectCoordinates(geo.coordinates, transformer),
  } as Geometry;
}

/**
 * If the FeatureCollection has a legacy `crs` property with a non-WGS84 CRS,
 * reproject all coordinates to EPSG:4326.
 */
async function reprojectIfNeeded(geojson: FeatureCollection): Promise<FeatureCollection> {
  const sourceCrs = extractNonWgs84Epsg(geojson as GeoJSONWithCrs);
  if (!sourceCrs) return geojson;

  // proj4 knows EPSG:4326 and EPSG:3857 by default.
  // For other codes, fetch the definition from epsg.io.
  if (!proj4.defs(sourceCrs)) {
    try {
      const resp = await fetch(`https://epsg.io/${sourceCrs.replace('EPSG:', '')}.proj4`);
      if (!resp.ok) throw new Error(`Unknown CRS: ${sourceCrs}`);
      const def = await resp.text();
      proj4.defs(sourceCrs, def);
    } catch {
      throw UploadErrorType.UnsupportedCRS;
    }
  }

  const transformer = proj4(sourceCrs, 'EPSG:4326');

  return {
    type: 'FeatureCollection',
    features: geojson.features.map((feature) => ({
      ...feature,
      geometry: feature.geometry
        ? reprojectGeometry(feature.geometry, transformer)
        : feature.geometry,
    })),
  };
}

/**
 * Check whether any coordinate in a set of features falls outside valid WGS84 bounds,
 * indicating the data is in a projected CRS.
 */
function hasOutOfBoundsCoordinates(features: Feature[]): boolean {
  const checkPosition = (pos: Position): boolean => Math.abs(pos[0]) > 180 || Math.abs(pos[1]) > 90;

  const checkCoords = (coords: unknown): boolean => {
    if (!Array.isArray(coords)) return false;
    if (typeof coords[0] === 'number') return checkPosition(coords as Position);

    return coords.some((coord) => checkCoords(coord));
  };

  return features.some(
    (feature) =>
      feature.geometry &&
      checkCoords((feature.geometry as Exclude<Geometry, GeoJSON.GeometryCollection>).coordinates)
  );
}

/**
 * Convert files to a GeoJSON
 * @param files Files to convert
 * @returns Error code if the convertion fails
 */
export async function convertFilesToGeojson(files: File[]): Promise<FeatureCollection> {
  // If multiple files are uploaded and one of them is a ShapeFile, this is the one we pass to the
  // loader because it is the one `ShapefileLoader` expects (out of the .prj, .shx, etc. other
  // Shapefile-related files). If the user uploaded files of a different extension, we just take the
  // first one.
  let fileToParse: File | ArrayBuffer = files.find((f) => f.name.endsWith('.shp')) ?? files[0];

  let loader: Loader;

  // We check that we have all the mandatory files to process a ShapeFile
  if (
    (fileToParse.name.endsWith('.shp') ||
      fileToParse.name.endsWith('.shx') ||
      fileToParse.name.endsWith('.dbf') ||
      fileToParse.name.endsWith('.prj')) &&
    files.length < 3
  ) {
    return Promise.reject(UploadErrorType.SHPMissingFile);
  }

  if (fileToParse.name.endsWith('.kmz')) {
    // In most of the cases, a .kmz file is just a zipped .kml file, but it can still contains
    // multiple files
    const fileMap = (await parse(fileToParse, ZipLoader)) as Awaited<
      ReturnType<typeof ZipLoader.parse>
    >;

    const kmlFileName = Object.keys(fileMap).find((name) => name.endsWith('.kml'));

    fileToParse = kmlFileName ? fileMap[kmlFileName] : null;

    loader = KMLLoader;
  } else {
    try {
      loader = await selectLoader(fileToParse, [ShapefileLoader, KMLLoader] as Loader[]);
    } catch (e) {
      return Promise.reject(UploadErrorType.UnsupportedFile);
    }
  }

  if (!loader) {
    return Promise.reject(UploadErrorType.UnsupportedFile);
  }

  const validationError = await validateFile(fileToParse, loader);
  if (validationError) {
    return Promise.reject(validationError);
  }

  let content: Awaited<ReturnType<typeof KMLLoader.parse | typeof ShapefileLoader.parse>>;

  try {
    content = (await load(fileToParse, loader, {
      gis: {
        format: 'geojson',
        // In case of Shapefile, if a .prj file is uploaded, we want to reproject the geometry
        reproject: true,
      },
      shp: {
        shape: 'geojson',
        // Shapefiles can hold up to 4 dimensions (XYZM). By default all dimensions are parsed;
        // when set to 2 only the X and Y dimensions are parsed. If not set, the resulting geometry
        // will not match the GeoJSON Specification (RFC 7946) and Google Maps will crash.
        // See: https://datatracker.ietf.org/doc/html/rfc7946#appendix-A.2
        _maxDimensions: 2,
      },
      // By default, some loaders like `ShapefileLoader` will fetch the companion files (.prj, .shx,
      // etc.) relative to where the .shp file is located. Yet, they are not served by an external
      // server so we reroute loaders.gl to the files the user uploaded.
      fetch: async (url: string | File): Promise<Response> => {
        let file: File;
        if (typeof url === 'string') {
          const extension = url.split('.').pop();
          file = files.find((f) => f.name.toLowerCase().endsWith(extension.toLowerCase()));
        } else {
          file = url;
        }

        if (file) {
          return Promise.resolve(new Response(file));
        }

        return Promise.resolve(new Response(null, { status: 404 }));
      },
    })) as Awaited<ReturnType<typeof KMLLoader.parse | typeof ShapefileLoader.parse>>;
  } catch (e) {
    return Promise.reject(UploadErrorType.UnsupportedFile);
  }

  let parsed: FeatureCollection;

  if (loader === ShapefileLoader) {
    const features = (content as Awaited<ReturnType<typeof ShapefileLoader.parse>>)
      .data as Feature[];
    const hasPrj = files.some((f) => f.name.toLowerCase().endsWith('.prj'));

    if (!hasPrj && hasOutOfBoundsCoordinates(features)) {
      return Promise.reject(UploadErrorType.SHPMissingPRJ);
    }

    parsed = {
      type: 'FeatureCollection',
      features,
    };
  } else {
    const feature = content as GeoJSONObject;
    if (isFeature(feature)) {
      parsed = featureCollection([feature]);
    } else {
      parsed = content as FeatureCollection;
    }
  }

  return reprojectIfNeeded(parsed);
}

/**
 * Appends valid polygon coordinates from polygon, multipolygon and geometry collection
 * geometry types into a shared multipolygon coordinates array.
 * @param geometry geometry to inspect
 * @param coordinates target multipolygon coordinates accumulator
 * @param removed counters for geometries that are excluded
 * @returns void
 */
const appendPolygonCoordinates = (
  geometry: Geometry | null | undefined,
  coordinates: MultiPolygon['coordinates'],
  removed: {
    nonPolygon: number;
    invalidPolygon: number;
  }
) => {
  if (!geometry) {
    removed.nonPolygon += 1;
    return;
  }

  switch (geometry.type) {
    case 'Polygon': {
      if (isStructurallyValidPolygonCoordinates(geometry.coordinates)) {
        coordinates.push(geometry.coordinates);
      } else {
        removed.invalidPolygon += 1;
      }
      break;
    }
    case 'MultiPolygon': {
      geometry.coordinates.forEach((polygonCoordinates) => {
        if (isStructurallyValidPolygonCoordinates(polygonCoordinates)) {
          coordinates.push(polygonCoordinates);
        } else {
          removed.invalidPolygon += 1;
        }
      });
      break;
    }
    case 'GeometryCollection':
      geometry.geometries.forEach((innerGeometry) =>
        appendPolygonCoordinates(innerGeometry as Geometry, coordinates, removed)
      );
      break;
    default:
      removed.nonPolygon += 1;
      break;
  }
};

export type ExtractPolygonsResult = {
  feature: Feature<MultiPolygon>;
  removed: {
    any: boolean;
    nonPolygon: number;
    invalidPolygon: number;
  };
};

/**
 * Extracts valid polygon and multipolygon geometries from GeoJSON and combines them into one multipolygon.
 * @param geoJSON input GeoJSON to extract from
 * @returns combined multipolygon feature and removal metadata
 */
export function extractPolygons(geoJSON: GeoJSONObject): ExtractPolygonsResult {
  try {
    const coordinates: MultiPolygon['coordinates'] = [];
    const removed = {
      nonPolygon: 0,
      invalidPolygon: 0,
    };

    if (isFeatureCollection(geoJSON)) {
      geoJSON.features.forEach((feature) =>
        appendPolygonCoordinates(feature.geometry as Geometry, coordinates, removed)
      );
    } else if (isFeature(geoJSON)) {
      appendPolygonCoordinates(geoJSON.geometry as Geometry, coordinates, removed);
    } else {
      appendPolygonCoordinates(geoJSON as Geometry, coordinates, removed);
    }

    if (coordinates.length === 0) {
      throw new Error('No polygon geometry found');
    }

    return {
      feature: {
        type: 'Feature',
        properties: null,
        geometry: {
          type: 'MultiPolygon',
          coordinates,
        },
      },
      removed: {
        any: removed.nonPolygon > 0 || removed.invalidPolygon > 0,
        nonPolygon: removed.nonPolygon,
        invalidPolygon: removed.invalidPolygon,
      },
    };
  } catch {
    throw UploadErrorType.NoPolygons;
  }
}
