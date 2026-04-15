import { FC, useEffect, useMemo } from 'react';

import { useQuery } from '@tanstack/react-query';
import type { GeoJSONObject } from '@turf/turf';
import axios, { isAxiosError } from 'axios';
import type { Feature } from 'geojson';
import { useAtomValue, useSetAtom } from 'jotai';

import { conservationStatsImpressed } from '@/components/analytics/heap';
import {
  modellingAtom,
  customLayersAtom,
  modellingCustomLayerIdAtom,
} from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { extractPolygons } from '@/lib/utils/file-upload';
import { ModellingData } from '@/types/modelling';

const fetchModelling = async (tab: string, feature: Feature) => {
  return axios.post<ModellingData>(process.env.NEXT_PUBLIC_ANALYSIS_CF_URL, {
    environment: tab,
    geometry: feature,
  });
};

const Modelling: FC = () => {
  const modellingLayerId = useAtomValue(modellingCustomLayerIdAtom);
  const customLayers = useAtomValue(customLayersAtom);
  const setModellingState = useSetAtom(modellingAtom);

  const [{ tab }] = useSyncMapContentSettings();

  const modellingLayer = modellingLayerId ? customLayers[modellingLayerId] : null;

  const feature = useMemo(() => {
    if (!modellingLayer) return null;
    try {
      return extractPolygons(modellingLayer.feature as GeoJSONObject).feature;
    } catch {
      return null;
    }
  }, [modellingLayer]);

  const getErrorMessageKey = (req: unknown): string => {
    if (!isAxiosError(req)) return 'general-stats-error';

    const status = req.response?.status;
    const error = req.response?.data?.error as string;

    if (status === 400) {
      if (error?.includes('Invalid geometry')) return 'invalid-geometry';
      return 'invalid-geometry';
    }

    return 'general-stats-error';
  };

  const { isFetching, isSuccess, data } = useQuery(
    ['modelling', tab, modellingLayerId],
    () => fetchModelling(tab, feature),
    {
      enabled: Boolean(feature) && ['marine', 'terrestrial'].includes(tab),
      select: ({ data }) => data,
      refetchOnWindowFocus: false,
      staleTime: Infinity,
      retry: false,
      onError: (req) => {
        setModellingState((prevState) => ({
          ...prevState,
          status: 'error',
          errorMessage: getErrorMessageKey(req),
        }));
      },
    }
  );

  useEffect(() => {
    if (isFetching) {
      setModellingState((prevState) => ({ ...prevState, status: 'running' }));
    } else if (isSuccess) {
      if (data?.locations_area?.length > 0) {
        setModellingState((prevState) => ({ ...prevState, status: 'success', data }));
        conservationStatsImpressed({
          countries: data.locations_area.flatMap((loc) => loc.code),
          environment: tab,
          area: data.total_area,
        });
      } else {
        setModellingState((prevState) => ({
          ...prevState,
          status: 'error',
          errorMessage: 'no-intersection-error',
        }));

        conservationStatsImpressed({
          countries: [],
          environment: tab,
        });
      }
    }
  }, [setModellingState, isFetching, isSuccess, data, tab]);

  return null;
};

export default Modelling;
