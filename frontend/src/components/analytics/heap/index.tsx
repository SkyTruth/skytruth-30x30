enum HeapEvents {
  CustomRegionEngaged = '30x30 Custom Region Engaged',
  CustomLayerEngaged = '30x30 Custom Layer Engaged',
  ConservationStatsImpressed = '30x30 Conservation Stats Impressed',
  LayerToggleEngaged = '30x30 Layer Toggle Engaged',
  ScreenshotEngaged = '30x30 Screenshot Engaged',
  LayersImpressed = '30x30 Layers Impressed',
}

export enum CustomRegionActions {
  Add = 'add',
  Clear = 'clear',
  Close = 'close',
  Create = 'create',
  View = 'view',
  Remove = 'remove',
}

type CustomRegionEngagedPayload = {
  action: CustomRegionActions;
  country?: string;
  custom_region?: string[];
};
export const customRegionEngaged = (payload: CustomRegionEngagedPayload) => {
  window.heap?.track(HeapEvents.CustomRegionEngaged, payload);
};

export enum CustomLayerActions {
  Create = 'create',
  Delete = 'delete',
  Rename = 'rename',
  Save = 'save',
  Stats = 'stats',
}

export enum CustomLayerMethods {
  Draw = 'draw',
  Upload = 'upload',
}

type CustomLayerEngagedPayload = {
  action: CustomLayerActions;
  bbox?: [number, number, number, number];
  fileType?: string;
  fileSize?: number;
  method?: CustomLayerMethods;
};

export const customLayerEngaged = (payload: CustomLayerEngagedPayload) => {
  window.heap?.track(HeapEvents.CustomLayerEngaged, payload);
};

type ConservationStatsImpressedPayload = {
  countries: string[];
  environment: string;
  area?: number;
};

export const conservationStatsImpressed = (payload: ConservationStatsImpressedPayload) => {
  window.heap?.track(HeapEvents.ConservationStatsImpressed, payload);
};

type LayerToggleEngagedPayload = {
  layerId: string;
  active: boolean;
};

export const layerToggleEngaged = (payload: LayerToggleEngagedPayload) => {
  window.heap?.track(HeapEvents.LayerToggleEngaged, payload);
};

export enum ScreenshotActions {
  Preview = 'preview',
  Download = 'download',
}

type ScreenshotEngagedPayload = {
  action: ScreenshotActions;
  bbox: [number, number, number, number];
  includeLegend: boolean;
};

export const screenshotEngaged = (payload: ScreenshotEngagedPayload) => {
  window.heap?.track(HeapEvents.ScreenshotEngaged, payload);
};

type LayersImpressedPayload = {
  layers: string[];
};

export const layersImpressed = (payload: LayersImpressedPayload) => {
  window.heap?.track(HeapEvents.LayersImpressed, payload);
};
