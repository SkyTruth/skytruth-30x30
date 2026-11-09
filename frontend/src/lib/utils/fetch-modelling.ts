import axios from 'axios';
import type { Feature } from 'geojson';

import { ModellingData } from '@/types/modelling';

// Strapi feature flag that sends modelling requests to cb_api
// TODO: TECH-3876, clean up the use_cb_api feature flag so cb_api is the only
// analysis backend; then drop `isCbApiActive` from the functions below
export const CB_API_FLAG = 'use_cb_api';

// TODO: TECH-3876, clean up the use_cb_api feature flag: drop the backend from the query key
export const getModellingQueryKey = (tab: string, layerId: string, isCbApiActive: boolean) => [
  'modelling',
  tab,
  layerId,
  isCbApiActive ? 'cb-api' : 'cloud-function',
];

const getCbApiUrl = (endpoint: string) =>
  `${process.env.NEXT_PUBLIC_CB_API_URL.replace(/\/+$/, '')}/${endpoint}`;

export const fetchModelling = (tab: string, feature: Feature, isCbApiActive: boolean) => {
  // TODO: TECH-3876, clean up the use_cb_api feature flag: remove NEXT_PUBLIC_ANALYSIS_CF_URL
  const url = isCbApiActive ? getCbApiUrl('coverage') : process.env.NEXT_PUBLIC_ANALYSIS_CF_URL;

  return axios.post<ModellingData>(url, {
    environment: tab,
    geometry: feature,
  });
};

export type ModellingStatEndpoint = 'protection-level' | 'habitats';

export const fetchModellingStat = (
  endpoint: ModellingStatEndpoint,
  feature: Feature,
  params: Record<string, string>
) =>
  axios.post<ModellingData>(getCbApiUrl(endpoint), {
    ...params,
    geometry: feature,
  });
