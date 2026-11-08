import { useQuery } from '@tanstack/react-query';

import useModellingFeature from '@/containers/map/content/map/modelling/use-modelling-feature';
import { fetchModellingStat, ModellingStatEndpoint } from '@/lib/utils/fetch-modelling';

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

  return useQuery(
    ['modelling-stat', endpoint, params, layerId],
    () => fetchModellingStat(endpoint, feature, params),
    {
      enabled: enabled && Boolean(feature),
      select: ({ data }) => data,
      refetchOnWindowFocus: false,
      staleTime: Infinity,
      retry: false,
    }
  );
};

export default useModellingStat;
