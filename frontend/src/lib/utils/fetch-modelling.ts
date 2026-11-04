import axios from 'axios';
import type { Feature } from 'geojson';

import { ModellingData } from '@/types/modelling';

// Strapi feature flag that sends modelling requests to cb_api
export const CB_API_FLAG = 'use_cb_api';

export const getModellingQueryKey = (tab: string, layerId: string, isCbApiActive: boolean) => [
  'modelling',
  tab,
  layerId,
  isCbApiActive ? 'cb-api' : 'cloud-function',
];

export const fetchModelling = (tab: string, feature: Feature, isCbApiActive: boolean) => {
  const url = isCbApiActive ? '/api/analysis/coverage' : process.env.NEXT_PUBLIC_ANALYSIS_CF_URL;

  return axios.post<ModellingData>(url, {
    environment: tab,
    geometry: feature,
  });
};
