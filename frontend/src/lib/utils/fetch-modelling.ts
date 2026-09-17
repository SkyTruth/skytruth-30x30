import axios from 'axios';
import type { Feature } from 'geojson';

import { ModellingData } from '@/types/modelling';

export const getModellingQueryKey = (tab: string, layerId: string) => ['modelling', tab, layerId];

export const fetchModelling = async (tab: string, feature: Feature) => {
  return axios.post<ModellingData>(process.env.NEXT_PUBLIC_ANALYSIS_CF_URL, {
    environment: tab,
    geometry: feature,
    // Only computed for marine environments
    ...(tab === 'marine' && { stats: ['fully-highly-protected'] }),
  });
};
