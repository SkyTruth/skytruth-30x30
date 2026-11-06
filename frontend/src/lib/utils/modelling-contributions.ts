import { ModellingLocationArea } from '@/types/modelling';

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
export const getAddedArea = ({ added_area, protected_area }: ModellingLocationArea) =>
  added_area ?? protected_area ?? 0;

// Total added area across locations
export const sumAddedArea = (
  locations: ModellingLocationArea[],
  exclude: ReadonlySet<string> = new Set()
) =>
  locations
    .filter(({ code }) => !exclude.has(code))
    .reduce((total, location) => total + getAddedArea(location), 0);
