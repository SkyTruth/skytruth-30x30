import { FC, useEffect, useMemo } from 'react';

import { useQuery } from '@tanstack/react-query';
import type { GeoJSONObject } from '@turf/turf';
import axios, { isAxiosError } from 'axios';
import type { Feature } from 'geojson';
import { useAtomValue, useSetAtom } from 'jotai';

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
      if (error?.includes('No data found')) return 'no-intersection-error';
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
    setModellingState((prevState) => ({
      ...prevState,
      ...(isSuccess && { status: 'success', data }),
      ...(isFetching && { status: 'running' }),
    }));
  }, [setModellingState, isFetching, isSuccess, data]);

  return null;
};

export default Modelling;
