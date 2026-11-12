export type ModellingLocation = {
  code: string;
  // Area of the drawn shape in this location that is not yet protected, in km²
  added_area: number;
};

export type ModellingData = {
  locations: ModellingLocation[];
  // Area of the drawn shape, in km²
  total_area: number;
};

// TODO: TECH-3876, remove the rest of this file with the analysis cloud function

// The same stats in the format the analysis cloud function returns
export type CloudFunctionModellingData = {
  locations_area: { code: string; protected_area: number }[];
  total_area: number;
};

export const toModellingData = (data: ModellingData | CloudFunctionModellingData): ModellingData =>
  'locations' in data
    ? data
    : {
        locations: data.locations_area.map(({ code, protected_area }) => ({
          code,
          added_area: protected_area,
        })),
        total_area: data.total_area,
      };
