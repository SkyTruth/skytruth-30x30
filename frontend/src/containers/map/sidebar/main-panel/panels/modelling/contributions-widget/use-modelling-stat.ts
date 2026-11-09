import { useQuery } from '@tanstack/react-query';
import type { Feature } from 'geojson';

import useModellingFeature from '@/containers/map/content/map/modelling/use-modelling-feature';
import { fetchModellingStat, ModellingStatEndpoint } from '@/lib/utils/fetch-modelling';

// Query for one cb_api stat of the drawn shape, cached per endpoint, params and shape
const getModellingStatQuery = (
  endpoint: ModellingStatEndpoint,
  params: Record<string, string>,
  feature: Feature | null,
  layerId: string,
  enabled: boolean
) => ({
  queryKey: ['modelling-stat', endpoint, params, layerId],
  queryFn: () => fetchModellingStat(endpoint, feature, params),
  enabled: enabled && Boolean(feature),
  select: ({ data }: Awaited<ReturnType<typeof fetchModellingStat>>) => data,
  refetchOnWindowFocus: false,
  staleTime: Infinity,
  retry: false,
});

/**
 * Added area per location for one cb_api stat (e.g. fully/highly protected) of the drawn
 * shape. Runs alongside the coverage request and loads and fails on its own
 */
const useModellingStat = (
  endpoint: ModellingStatEndpoint,
  params: Record<string, string>,
  { enabled = true }: { enabled?: boolean } = {}
) => {
  const { feature, layerId } = useModellingFeature();

  return useQuery(getModellingStatQuery(endpoint, params, feature, layerId, enabled));
};

export default useModellingStat;
