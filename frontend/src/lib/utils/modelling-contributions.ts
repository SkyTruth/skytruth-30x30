import { ModellingLocationArea } from '@/types/modelling';

// Strapi location code of the whole world, shown in the Global section
export const GLOBAL_CODE = 'GLOB';

/**
 * How much of an area is protected before and after a drawn shape,
 * shown in one stat block of the Conservation Builder panel
 */
export type Contribution = {
  // Area already protected, in km²
  existing: number;
  // Area the drawn shape newly protects, in km²
  added: number;
  // Total area, in km²
  total: number;
  // Each as a percentage of total, from 0 to 100
  existingPercentage: number;
  addedPercentage: number;
  totalPercentage: number;
};

/**
 * Combine the area already protected with the area a drawn shape adds
 *
 * The added area is capped at the unprotected area: rounding and differences in data
 * resolution can make the analysis report more added area than is left unprotected
 */
export const computeContribution = (
  existing: number,
  added: number,
  total: number
): Contribution => {
  const unprotected = Math.max(total - existing, 0);
  const cappedAdded = Math.min(Math.max(added, 0), unprotected);

  const toPercentage = (area: number) => (total > 0 ? (area / total) * 100 : 0);
  const existingPercentage = toPercentage(existing);
  const addedPercentage = toPercentage(cappedAdded);

  return {
    existing,
    added: cappedAdded,
    total,
    existingPercentage,
    addedPercentage,
    totalPercentage: existingPercentage + addedPercentage,
  };
};

// Added area for one location in an analysis result, in km²
// TODO: TECH-3876, clean up the use_cb_api feature flag: drop the protected_area
// fallback, which only the analysis cloud function returns
export const getAddedArea = ({ added_area, protected_area }: ModellingLocationArea) => {
  const area = added_area ?? protected_area ?? 0;

  // 0s in the analysis result indicate small overlaps that were rounded to 0,
  // so use EPSILON (a tiny non-zero value) to show "<1 km²" and "+<0.1%" in the frontend
  return area === 0 ? Number.EPSILON : area;
};

// Total added area across locations
export const sumAddedArea = (
  locations: ModellingLocationArea[],
  exclude: ReadonlySet<string> = new Set()
) =>
  locations
    .filter(({ code }) => !exclude.has(code))
    .reduce((total, location) => total + getAddedArea(location), 0);

/** Existing protected area and total area of one location for a stat in km² */
export type Baseline = {
  code: string;
  existing: number;
  total: number;
};

/**
 * Contribution per location code for one stat (e.g. coverage):
 * baseline and added area from an analysis result.
 * `GLOBAL_CODE` gets the added area of every location in the analysis except `exclude`
 */
export const buildContributions = (
  baselines: Baseline[],
  locations: ModellingLocationArea[],
  exclude: ReadonlySet<string> = new Set()
) => {
  const addedByCode = new Map(locations.map((location) => [location.code, getAddedArea(location)]));

  return new Map(
    baselines.map(({ code, existing, total }) => {
      const added =
        code === GLOBAL_CODE ? sumAddedArea(locations, exclude) : (addedByCode.get(code) ?? 0);
      return [code, computeContribution(existing, added, total)] as const;
    })
  );
};
