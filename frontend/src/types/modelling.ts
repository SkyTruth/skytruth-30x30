export type ModellingLocationArea = {
  code: string;
  protected_area: number;
};

export type ModellingStats = {
  locations_area: ModellingLocationArea[];
  total_area: number;
  total_protected_area: number;
};

export type ModellingData = ModellingStats & {
  // Marine only: the portion of the drawn area that isn't already fully/highly protected
  fully_highly_protected?: ModellingStats;
};
