import { QueryClient, dehydrate } from '@tanstack/react-query';
import type { GetServerSideProps } from 'next';

import { PAGES } from '@/constants/pages';
import MapLayout from '@/layouts/map';
import { fetchTranslations } from '@/lib/i18n';
import mapParamsToSearchParams from '@/lib/mapparams-to-searchparams';
import { FCWithMessages } from '@/types';
import { getGetLocationsQueryKey, getGetLocationsQueryOptions } from '@/types/generated/location';
import { LocationListResponse } from '@/types/generated/strapi.schemas';

import { LayoutProps } from '../_app';

const ProgressTrackerPage: FCWithMessages & {
  layout: LayoutProps<{ locale: string; location: { code: string; name: string } }>;
} = () => {
  return null;
};

ProgressTrackerPage.layout = {
  Component: MapLayout,
  props: ({ locale, location }) => {
    let locationNameField = 'name';
    if (locale === 'es') {
      locationNameField = 'name_es';
    }
    if (locale === 'fr') {
      locationNameField = 'name_fr';
    }

    return {
      title: location?.[locationNameField],
    };
  },
};

ProgressTrackerPage.messages = ['pages.progress-tracker', ...MapLayout.messages];

export const getServerSideProps: GetServerSideProps = async (context) => {
  const { query } = context;
  const { locationCode = 'GLOB', location, mapParams = null } = query;

  if (mapParams) {
    const searchParams = mapParamsToSearchParams(mapParams);
    const target = `/${context.locale}/${PAGES.progressTracker}/${location}?${searchParams}`;

    return {
      redirect: {
        permanent: false,
        destination: target,
      },
    };
  }

  const queryClient = new QueryClient();

  await queryClient.prefetchQuery({
    ...getGetLocationsQueryOptions({
      locale: context.locale,
      filters: {
        code: locationCode,
      },
    }),
  });

  const locationsData = queryClient.getQueryData<LocationListResponse>(
    getGetLocationsQueryKey({
      locale: context.locale,
      filters: {
        code: locationCode,
      },
    })
  );

  if (!locationsData || !locationsData.data) return { notFound: true };

  return {
    props: {
      locale: context.locale,
      location: locationsData.data[0].attributes,
      dehydratedState: dehydrate(queryClient),
      messages: await fetchTranslations(context.locale, ProgressTrackerPage.messages),
    },
  };
};

export default ProgressTrackerPage;
