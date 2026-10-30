import { ComponentProps } from 'react';

import { QueryClient, dehydrate } from '@tanstack/react-query';
import type { GetServerSideProps } from 'next';

import { PAGES } from '@/constants/pages';
import MapLayout from '@/layouts/map';
import { fetchTranslations } from '@/lib/i18n';
import mapParamsToSearchParams from '@/lib/mapparams-to-searchparams';
import { getServiceUnavailableProps, isBackendDown } from '@/lib/service-unavailable';
import { FCWithMessages } from '@/types';
import { getGetLocationsQueryKey, getGetLocationsQueryOptions } from '@/types/generated/location';
import { LocationListResponse } from '@/types/generated/strapi.schemas';
import { MapTypes } from '@/types/map';

import { LayoutProps } from '../_app';

const ProgressTrackerPage: FCWithMessages & {
  layout: LayoutProps<
    { locale: string; location: { code: string; type: string } },
    ComponentProps<typeof MapLayout>
  >;
} = () => {
  return null;
};

ProgressTrackerPage.layout = {
  Component: MapLayout,
  props: ({ location }) => ({
    location,
    type: MapTypes.ProgressTracker,
  }),
};

ProgressTrackerPage.messages = ['pages.progress-tracker', ...MapLayout.messages];

export const getServerSideProps: GetServerSideProps = async (context) => {
  const { query } = context;
  const { locationCode = 'GLOB', location, mapParams = null, 'run-as-of': runAsOf } = query;

  if (mapParams) {
    let searchParams = mapParamsToSearchParams(mapParams);
    if (runAsOf) {
      searchParams += `&run-as-of=${runAsOf}`;
    }

    const target = `/${context.locale}${PAGES.progressTracker}/${location}?${searchParams}`;

    return {
      redirect: {
        permanent: false,
        destination: target,
      },
    };
  }

  const queryClient = new QueryClient();

  const locationsParams = {
    locale: context.locale,
    filters: {
      code: locationCode,
    },
  };

  await queryClient.prefetchQuery({
    ...getGetLocationsQueryOptions(locationsParams),
  });

  const locationsKey = getGetLocationsQueryKey(locationsParams);
  const locationsData = queryClient.getQueryData<LocationListResponse>(locationsKey);

  if (isBackendDown(queryClient.getQueryState(locationsKey)?.error)) {
    return getServiceUnavailableProps(context);
  }

  if (!locationsData?.data?.length) return { notFound: true };

  return {
    props: {
      locale: context.locale,
      location: locationsData.data[0],
      dehydratedState: dehydrate(queryClient),
      messages: await fetchTranslations(context.locale, ProgressTrackerPage.messages),
    },
  };
};

export default ProgressTrackerPage;
