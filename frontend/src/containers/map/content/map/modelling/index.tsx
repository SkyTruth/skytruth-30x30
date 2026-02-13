import { useEffect } from 'react';

import { useQuery } from '@tanstack/react-query';
import axios, { isAxiosError } from 'axios';
import type { Feature } from 'geojson';
import { useAtomValue, useSetAtom } from 'jotai';
import { useTranslations } from 'next-intl';

import { modellingAtom, drawStateAtom } from '@/containers/map/store';
import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { FCWithMessages } from '@/types';
import { ModellingData } from '@/types/modelling';

const fetchModelling = async (tab: string, feature: Feature) => {
  return axios.post<ModellingData>(process.env.NEXT_PUBLIC_ANALYSIS_CF_URL, {
    environment: tab,
    geometry: feature,
  });
};

const Modelling: FCWithMessages = () => {
  const t = useTranslations('components.widget');

  const { feature, revision } = useAtomValue(drawStateAtom);
  const setModellingState = useSetAtom(modellingAtom);

  const [{ tab }] = useSyncMapContentSettings();

  const getErrorMessage = (error) => {
    if (error.includes('Invalid input geometry')) {
      return t('invalid-geometry');
    }
    return error;
  };

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
            errorMessage:
              req.response?.status === 400 ? getErrorMessage(req.response?.data.error) : undefined,
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

Modelling.messages = ['components.widget'];

export default Modelling;
