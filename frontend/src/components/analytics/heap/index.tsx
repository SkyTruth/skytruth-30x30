enum HeapEvents {
  CustomRegionEngaged = '30x30 Custom Region Engaged',
}

export enum CustomRegionActions {
  Add = 'add',
  Clear = 'clear',
  Close = 'close',
  Create = 'create',
  View = 'view',
  Remove = 'remove',
}

interface CustomRegionEngagedPayload {
  action: CustomRegionActions;
  country?: string;
  custom_region?: string[];
}
export const customRegionEngaged = (payload: CustomRegionEngagedPayload) => {
  if (!window.heap) {
    return;
  }

  window.heap.track(HeapEvents.CustomRegionEngaged, payload);
};
