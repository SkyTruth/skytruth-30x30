import { useQueries, useQuery } from '@tanstack/react-query';
import type { Feature } from 'geojson';

import {
  fetchModellingStat,
  ModellingStatData,
  ModellingStatEndpoint,
} from '@/lib/utils/fetch-modelling';

import useModellingFeature from './use-modelling-feature';

// Query for one cb_api stat of the drawn shape, cached per endpoint, params and shape
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

/**
 * Added area per location for one cb_api stat (e.g. fully/highly protected) of the drawn
 * shape. Runs alongside the coverage request and loads and fails on its own
 */
const useModellingStat = <E extends ModellingStatEndpoint>(
  endpoint: E,
  params: Record<string, string>,
  { enabled = true }: { enabled?: boolean } = {}
) => {
  const { feature, layerId } = useModellingFeature();

  return useQuery(getModellingStatQuery(endpoint, params, feature, layerId, enabled));
};

// Slug of the fully/highly protected level, in cb_api and in Strapi
export const FHP_LEVEL = 'fully-highly-protected';

/**
 * cb_api's fully/highly protected analysis of the drawn shape (marine only): the added area
 * per location. Every caller shares one cached request
 */
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
