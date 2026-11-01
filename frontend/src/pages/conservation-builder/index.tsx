import { ComponentProps } from 'react';

import { QueryClient, dehydrate } from '@tanstack/react-query';
import type { GetServerSideProps } from 'next';

import { PAGES } from '@/constants/pages';
import MapLayout from '@/layouts/map';
import { fetchTranslations } from '@/lib/i18n';
import mapParamsToSearchParams from '@/lib/mapparams-to-searchparams';
import { FCWithMessages } from '@/types';
import { MapTypes } from '@/types/map';

import { LayoutProps } from '../_app';

const ConservationBuilderPage: FCWithMessages & {
  layout: LayoutProps<Record<string, never>, ComponentProps<typeof MapLayout>>;
} = () => {
  return null;
};

ConservationBuilderPage.layout = {
  Component: MapLayout,
  props: {
    type: MapTypes.ConservationBuilder,
  },
};

ConservationBuilderPage.messages = ['pages.conservation-builder', ...MapLayout.messages];

// Conservation Builder has no summary tab, so default to terrestrial if the URL has no valid tab
const CONSERVATION_BUILDER_CONTENT = JSON.stringify({ showDetails: false, tab: 'terrestrial' });

const isConservationBuilderTab = (tab: unknown) =>
  ['terrestrial', 'marine'].includes(tab as string);

const hasConservationBuilderTab = (content: unknown) => {
  try {
    return isConservationBuilderTab(JSON.parse(content as string)?.tab);
  } catch {
    return false;
  }
};

export const getServerSideProps: GetServerSideProps = async (context) => {
  const { query } = context;
  const { mapParams = null, 'run-as-of': runAsOf } = query;

  if (mapParams) {
    // Keep the previous page's settings (summary on PT goes to terrestrial on CB),
    // except with showDetails always false
    const params = JSON.parse(mapParams as string);
    const tab = params.content?.tab;
    params.content = {
      ...params.content,
      showDetails: false,
      tab: isConservationBuilderTab(tab) ? tab : 'terrestrial',
    };

    let searchParams = mapParamsToSearchParams(JSON.stringify(params));
    if (runAsOf) {
      searchParams += `&run-as-of=${runAsOf}`;
    }

    const target = `/${context.locale}${PAGES.conservationBuilder}/?${searchParams}`;

    return {
      redirect: {
        permanent: false,
        destination: target,
      },
    };
  }

  // Redirect URLs with a missing, summary or invalid tab to the default tab
  if (!hasConservationBuilderTab(query.content)) {
    const searchParams = new URLSearchParams(query as Record<string, string>);
    searchParams.set('content', CONSERVATION_BUILDER_CONTENT);

    return {
      redirect: {
        permanent: false,
        destination: `/${context.locale}${PAGES.conservationBuilder}?${searchParams}`,
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
