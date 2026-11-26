import { ModellingLocationArea } from '@/types/modelling';

export const GLOBAL_CODE = 'GLOB';

export type Contribution = {
  existing: number;
  added: number;
  total: number;
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
const computeContribution = (existing: number, added: number, total: number): Contribution => {
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

const sumAddedArea = (
  locations: ModellingLocationArea[],
  exclude: ReadonlySet<string> = new Set()
) =>
  locations
    .filter(({ code }) => !exclude.has(code))
    .reduce((total, location) => total + location.protected_area, 0);

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
  const addedByCode = new Map(
    locations.map((location) => [location.code, location.protected_area])
  );

  return new Map(
    baselines.map(({ code, existing, total }) => {
      const added =
        code === GLOBAL_CODE ? sumAddedArea(locations, exclude) : (addedByCode.get(code) ?? 0);
      return [code, computeContribution(existing, added, total)] as const;
    })
  );
};
