enum HeapEvents {
  CustomRegionEngaged = '30x30 Custom Region Engaged',
  CustomLayerEngaged = '30x30 Custom Layer Engaged',
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
  if (!window.heap) {
    return;
  }
  window.heap.track(HeapEvents.CustomRegionEngaged, payload);
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
  if (!window.heap) {
    return;
  }
  window.heap.track(HeapEvents.CustomLayerEngaged, payload);
};
