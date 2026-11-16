export type ModellingLocationArea = {
  code: string;
  protected_area: number;
};

export type ModellingData = {
  locations_area: ModellingLocationArea[];
  total_area: number;
  total_protected_area: number;
};
