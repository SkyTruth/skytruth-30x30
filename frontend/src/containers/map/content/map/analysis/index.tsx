import { useEffect } from 'react';

import { useQuery } from '@tanstack/react-query';
// import axios from 'axios';
// import { Feature } from 'geojson';
import { useAtomValue, useSetAtom } from 'jotai';

import { analysisAtom, drawStateAtom } from '@/containers/map/store';

const fetchAnalysis = async () => {
  // todo: prepare feature for analysis
  // return axios.post('https://analysis.skytruth.org', feature);

  return new Promise((resolve) => {
    setTimeout(() => {
      resolve({
        locations_area: [
          { code: 'FRA', protected_area: 2385406 },
          { code: 'USA', protected_area: 5000367 },
        ],
        total_area: 73600000,
      });
    }, 2500);
  });
};

const Analysis = () => {
  const { feature } = useAtomValue(drawStateAtom);
  const setAnalysisState = useSetAtom(analysisAtom);

  const { isFetching, isSuccess, data, isError } = useQuery(
    ['analysis', feature],
    () => fetchAnalysis(),
    {
      enabled: Boolean(feature),
    }
  );

  useEffect(() => {
    setAnalysisState((prevState) => ({
      ...prevState,
      ...(isSuccess && { status: 'success', data }),
      ...(isFetching && { status: 'running' }),
      ...(isError && { status: 'error' }),
    }));
  }, [setAnalysisState, isFetching, isSuccess, data, isError]);

  return null;
};

export default Analysis;
