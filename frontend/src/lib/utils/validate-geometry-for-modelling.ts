import type { QueryClient } from '@tanstack/react-query';
import axios from 'axios';
import type { Feature } from 'geojson';

import { ModellingData } from '@/types/modelling';

const fetchModelling = async (tab: string, feature: Feature) => {
  return axios.post<ModellingData>(process.env.NEXT_PUBLIC_ANALYSIS_CF_URL, {
    environment: tab,
    geometry: feature,
  });
};

/**
 * Validates a geometry by calling the analysis API via React Query's fetchQuery.
 * On success the result is cached under ['modelling', tab, layerId] so the
 * Modelling component gets a cache hit and avoids a duplicate request.
 */
export async function validateGeometryForModelling(
  queryClient: QueryClient,
  tab: string,
  layerId: string,
  feature: Feature
): Promise<{ valid: boolean }> {
  try {
    await queryClient.fetchQuery(['modelling', tab, layerId], () => fetchModelling(tab, feature), {
      staleTime: Infinity,
      retry: false,
    });
    return { valid: true };
  } catch (error) {
    if (axios.isAxiosError(error) && error.response?.status === 400) {
      const data = error.response.data;
      if (typeof data === 'string' && data.includes('Invalid geometry')) {
        return { valid: false };
      }
      if (typeof data === 'object' && data !== null) {
        const message =
          (data as Record<string, unknown>).message ?? (data as Record<string, unknown>).error;
        if (typeof message === 'string' && message.includes('Invalid geometry')) {
          return { valid: false };
        }
      }
    }
    // Network errors, 500s, etc. — let the modelling component handle these later
    return { valid: true };
  }
}
