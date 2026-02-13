import { useEffect } from 'react';

import { useQuery } from '@tanstack/react-query';
import axios, { isAxiosError } from 'axios';
import type { Feature } from 'geojson';
import { useAtomValue, useSetAtom } from 'jotai';

import { modellingAtom, drawStateAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { ModellingData } from '@/types/modelling';

const fetchModelling = async (tab: string, feature: Feature) => {
  return axios.post<ModellingData>(process.env.NEXT_PUBLIC_ANALYSIS_CF_URL, {
    environment: tab,
    geometry: feature,
  });
};

const Modelling = () => {
  const { feature, revision } = useAtomValue(drawStateAtom);
  const setModellingState = useSetAtom(modellingAtom);

  const [{ tab }] = useSyncMapContentSettings();

  const { isFetching, isSuccess, data } = useQuery(
    ['modelling', tab, revision, feature],
    () => fetchModelling(tab, feature),
    {
      enabled: Boolean(feature) && ['marine', 'terrestrial'].includes(tab),
      select: ({ data }) => data,
      refetchOnWindowFocus: false,
      retry: false,
      onError: (req) => {
        if (isAxiosError(req)) {
          setModellingState((prevState) => ({
            ...prevState,
            status: 'error',
            errorMessage: req.response?.status === 400 ? req.response?.data.error : undefined,
          }));
        } else {
          setModellingState((prevState) => ({
            ...prevState,
            status: 'error',
            errorMessage: undefined,
          }));
        }
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
