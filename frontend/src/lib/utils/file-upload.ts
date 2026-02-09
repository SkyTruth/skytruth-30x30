import { selectLoader, load, parse } from '@loaders.gl/core';
import { KMLLoader } from '@loaders.gl/kml';
import { Loader } from '@loaders.gl/loader-utils';
import { ShapefileLoader } from '@loaders.gl/shapefile';
import { ZipLoader } from '@loaders.gl/zip';
import { featureCollection, GeoJSONObject, Geometries, MultiPolygon, Polygon } from '@turf/turf';
import type { Feature, FeatureCollection, GeometryCollection } from 'geojson';

export type ValidGeometryType = Polygon | MultiPolygon | GeometryCollection;

export enum UploadErrorType {
  Generic,
  InvalidXMLSyntax,
  SHPMissingFile,
  UnsupportedFile,
}

export const supportedFileformats = [
  ...KMLLoader.extensions,
  ...['kmz'],
  ...['shp', 'prj', 'shx', 'dbf', 'cfg'],
  ...['geojson'],
];

const isFeatureCollection = (
  geoJSON: GeoJSONObject
): geoJSON is FeatureCollection<Geometries, unknown> => geoJSON.type === 'FeatureCollection';

const isFeature = (geoJSON: GeoJSONObject): geoJSON is Feature<Geometries, unknown> =>
  geoJSON.type === 'Feature';

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
      loader = await selectLoader(fileToParse, [ShapefileLoader, KMLLoader]);
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
    parsed = {
      type: 'FeatureCollection',
      features: (content as Awaited<ReturnType<typeof ShapefileLoader.parse>>).data as Feature[],
    };
  } else {
    const feature = content as GeoJSONObject;
    if (isFeature(feature)) {
      parsed = featureCollection([feature]);
    } else {
      parsed = content as FeatureCollection;
    }
  }

  return parsed;
}

// Currently unused, but left as an export since it iwll be helpful with uplaoding geometries
// to Conservation Builder
export function cleanupGeoJSON(geoJSON: GeoJSONObject): Feature<ValidGeometryType> {
  let collection: FeatureCollection;
  if (isFeature(geoJSON)) {
    collection = featureCollection([geoJSON]);
  } else if (isFeatureCollection(geoJSON)) {
    collection = geoJSON;
  } else {
    return;
  }

  const features: Feature<ValidGeometryType>[] = collection.features.filter(
    (f) =>
      f.geometry?.type === 'MultiPolygon' ||
      f.geometry?.type === 'Polygon' ||
      f.geometry?.type === 'GeometryCollection'
  ) as Feature<ValidGeometryType>[];

  // NOTE: Only the first feature is imported
  const feature = features[0];
  if (!feature) {
    // No feature with polygon or multipolygon found in geojson
    throw new Error();
  }

  return feature;
}
