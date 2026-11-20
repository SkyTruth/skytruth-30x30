export type ModellingLocationArea = {
  code: string;
  protected_area: number;
};

export type ModellingData = {
  locations_area: ModellingLocationArea[];
  total_area: number;
  total_protected_area: number;
};

// TODO: TECH-3876, clean up the use_cb_api feature flag: make cb_api's format below
// the ModellingData type and remove the conversion

// The same stats in the format cb_api returns
export type CbApiModellingData = {
  locations: {
    code: string;
    // Area of the drawn shape in this location that is not yet protected, in km²
    added_area: number;
  }[];
  // Area of the drawn shape, in km²
  total_area: number;
};

export const fromCbApiModellingData = (data: CbApiModellingData): ModellingData => {
  const locationsArea = data.locations.map(({ code, added_area }) => ({
    code,
    protected_area: added_area,
  }));

  return {
    locations_area: locationsArea,
    total_area: data.total_area,
    total_protected_area: locationsArea.reduce(
      (acc, { protected_area }) => acc + protected_area,
      0
    ),
  };
};

// Habitat stats in the format cb_api returns: the added area per location and habitat
export type CbApiHabitatsData = {
  locations: {
    code: string;
    habitats: {
      // cb_api's habitat slug
      habitat: string;
      // Area of this habitat in the drawn shape and location that is not yet protected, in km²
      added_area: number;
    }[];
  }[];
  // Area of the drawn shape, in km²
  total_area: number;
};

// Splits cb_api's habitat stats into the coverage format, one result per habitat slug
// A habitat the shape doesn't add anywhere has no entry
export const fromCbApiHabitatsData = (data: CbApiHabitatsData): Record<string, ModellingData> => {
  const byHabitat: Record<string, CbApiModellingData> = {};
  data.locations.forEach(({ code, habitats }) =>
    habitats.forEach(({ habitat, added_area }) => {
      byHabitat[habitat] ??= { locations: [], total_area: data.total_area };
      byHabitat[habitat].locations.push({ code, added_area });
    })
  );

  return Object.fromEntries(
    Object.entries(byHabitat).map(([habitat, stats]) => [habitat, fromCbApiModellingData(stats)])
  );
};
