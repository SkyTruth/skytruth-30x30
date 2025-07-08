import { ComponentProps } from 'react';

import { QueryClient, dehydrate } from '@tanstack/react-query';
import type { GetServerSideProps } from 'next';

import { PAGES } from '@/constants/pages';
import MapLayout from '@/layouts/map';
import { fetchTranslations } from '@/lib/i18n';
import mapParamsToSearchParams from '@/lib/mapparams-to-searchparams';
import { FCWithMessages } from '@/types';

import { LayoutProps } from '../_app';

const ConservationBuilderPage: FCWithMessages & {
  layout: LayoutProps<Record<string, never>, ComponentProps<typeof MapLayout>>;
} = () => {
  return null;
};

ConservationBuilderPage.layout = {
  Component: MapLayout,
  props: {
    title: '',
    type: 'conservation-builder',
  },
};

ConservationBuilderPage.messages = ['pages.conservation-builder', ...MapLayout.messages];

export const getServerSideProps: GetServerSideProps = async (context) => {
  const { query } = context;
  const { mapParams = null, runAsOf } = query;

  if (mapParams) {
    let searchParams = mapParamsToSearchParams(mapParams);
    if (runAsOf) {
      searchParams += `&runAsOf=${runAsOf}`;
    }

    const target = `/${context.locale}/${PAGES.conservationBuilder}/?${searchParams}`;

    return {
      redirect: {
        permanent: false,
        destination: target,
      },
    };
  }

  const queryClient = new QueryClient();

  return {
    props: {
      dehydratedState: dehydrate(queryClient),
      messages: await fetchTranslations(context.locale, ConservationBuilderPage.messages),
    },
  };
};

export default ConservationBuilderPage;
