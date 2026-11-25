import { useQuery } from '@tanstack/react-query';
import type { Feature } from 'geojson';

import useModellingFeature from '@/hooks/use-modelling-feature';
import { fetchModellingStat, ModellingStatEndpoint } from '@/lib/utils/fetch-modelling';

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

const useModellingStat = (
  endpoint: ModellingStatEndpoint,
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

export default useModellingStat;
