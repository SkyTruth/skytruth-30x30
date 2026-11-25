import { useQueries, useQuery } from '@tanstack/react-query';
import type { Feature } from 'geojson';

import useModellingFeature from '@/hooks/use-modelling-feature';
import {
  fetchModellingStat,
  ModellingStatData,
  ModellingStatEndpoint,
} from '@/lib/utils/fetch-modelling';

const getModellingStatQuery = <E extends ModellingStatEndpoint>(
  endpoint: E,
  params: Record<string, string>,
  feature: Feature | null,
  layerId: string,
  enabled: boolean
) => ({
  queryKey: ['modelling-stat', endpoint, params, layerId],
  queryFn: () => fetchModellingStat(endpoint, feature, params),
  enabled: enabled && Boolean(feature),
  select: ({ data }: { data: ModellingStatData<E> }) => data,
  refetchOnWindowFocus: false,
  staleTime: Infinity,
  retry: false,
});

const useModellingStat = <E extends ModellingStatEndpoint>(
  endpoint: E,
  params: Record<string, string>,
  { enabled = true }: { enabled?: boolean } = {}
) => {
  const { feature, layerId } = useModellingFeature();

  return useQuery(getModellingStatQuery(endpoint, params, feature, layerId, enabled));
};

// Same slug in cb_api and Strapi
export const FHP_LEVEL = 'fully-highly-protected';

export const useFhpAnalysis = (enabled: boolean) =>
  useModellingStat('protection-level', { level: FHP_LEVEL, environment: 'marine' }, { enabled });

/**
 * The same as `useModellingStat` for several requests to one endpoint in parallel (e.g. one
 * per marine habitat), each loading and failing on its own. Results are in the order of `paramsList`
 */
export const useModellingStats = <E extends ModellingStatEndpoint>(
  endpoint: E,
  paramsList: Record<string, string>[],
  { enabled = true }: { enabled?: boolean } = {}
) => {
  const { feature, layerId } = useModellingFeature();

  return useQueries({
    queries: paramsList.map((params) =>
      getModellingStatQuery(endpoint, params, feature, layerId, enabled)
    ),
  });
};

export default useModellingStat;
