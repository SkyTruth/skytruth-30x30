export type ModellingLocationArea = {
  code: string;
  // Area of the drawn shape in this location that is not yet protected, in km²
  added_area?: number;
  // The same value under the name the analysis cloud function still uses
  protected_area?: number;
};

export type ModellingData = {
  locations_area: ModellingLocationArea[];
  // Area of the drawn shape, in km²
  total_area: number;
};
