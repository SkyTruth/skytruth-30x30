import axios from 'axios';
import type { Feature } from 'geojson';

import {
  fromCbApiHabitatsData,
  fromCbApiModellingData,
  type CbApiHabitatsData,
  type CbApiModellingData,
  type ModellingData,
} from '@/types/modelling';

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

export const fetchModelling = async (tab: string, feature: Feature, isCbApiActive: boolean) => {
  const body = { environment: tab, geometry: feature };

  // TODO: TECH-3876, clean up the use_cb_api feature flag: remove NEXT_PUBLIC_ANALYSIS_CF_URL
  if (!isCbApiActive) {
    return axios.post<ModellingData>(process.env.NEXT_PUBLIC_ANALYSIS_CF_URL, body);
  }

  const response = await axios.post<CbApiModellingData>(getCbApiUrl('coverage'), body);
  return { ...response, data: fromCbApiModellingData(response.data) };
};

// Each cb_api stat endpoint's response, converted to the format of the coverage results
const STAT_CONVERSIONS = {
  'protection-level': (data: CbApiModellingData) => fromCbApiModellingData(data),
  // One result per habitat slug
  habitats: (data: CbApiHabitatsData) => fromCbApiHabitatsData(data),
};

export type ModellingStatEndpoint = keyof typeof STAT_CONVERSIONS;

export type ModellingStatData<E extends ModellingStatEndpoint> = ReturnType<
  (typeof STAT_CONVERSIONS)[E]
>;

// One cb_api stat for the drawn shape (e.g. fully/highly protected), converted to the
// format of the coverage results
export const fetchModellingStat = async <E extends ModellingStatEndpoint>(
  endpoint: E,
  feature: Feature,
  params: Record<string, string>
) => {
  const response = await axios.post(getCbApiUrl(endpoint), { ...params, geometry: feature });
  return {
    ...response,
    data: STAT_CONVERSIONS[endpoint](response.data) as ModellingStatData<E>,
  };
};
