import { useMemo, useRef } from 'react';

import { QueryClient, dehydrate } from '@tanstack/react-query';
import { GetServerSideProps } from 'next';
import { useLocale, useTranslations } from 'next-intl';

import Section, {
  SectionTitle,
  SectionDescription,
  SectionContent,
} from '@/components/static-pages/section';
import StatsImage from '@/components/static-pages/stats-image';
import TwoColSubsection from '@/components/static-pages/two-col-subsection';
import EarthSurfaceCoverage from '@/containers/homepage/earth-surface-coverage';
import InteractiveMap from '@/containers/homepage/interactive-map';
import Intro from '@/containers/homepage/intro';
import LinkCards from '@/containers/homepage/link-cards';
import useScrollSpy from '@/hooks/use-scroll-spy';
import Layout, { Content, Sidebar } from '@/layouts/static-page';
import { fetchTranslations } from '@/lib/i18n';
import { formatPercentage } from '@/lib/utils/formats';
import { FCWithMessages } from '@/types';
import {
  getGetProtectionCoverageStatsQueryKey,
  getGetProtectionCoverageStatsQueryOptions,
} from '@/types/generated/protection-coverage-stat';
import {
  getGetStaticIndicatorsQueryKey,
  getGetStaticIndicatorsQueryOptions,
} from '@/types/generated/static-indicator';
import {
  StaticIndicator,
  StaticIndicatorListResponse,
  ProtectionCoverageStatListResponse,
} from '@/types/generated/strapi.schemas';

const STATIC_INDICATOR_MAPPING = {
  biodiversity: 'species-threatened-with-extinction',
  climate: 'earth-co2-stored-cycled',
  livesLivelihoods: 'lives-impact',
  biodiversityTextNumber: 'species-threathened-number',
  biodiversityTextOcean: 'protected-world-ocean-percentage',
  biodiversityTextLand: 'protected-land-area-percentage',
};

const Home: FCWithMessages = ({
  staticIndicators,
  protectionCoverageStats,
}: {
  staticIndicators: StaticIndicatorListResponse;
  protectionCoverageStats: ProtectionCoverageStatListResponse;
}) => {
  const t = useTranslations('pages.home');
  const locale = useLocale();

  const sections = {
    services: {
      id: 'services',
      name: t('services'),
      ref: useRef<HTMLDivElement>(null),
    },
    impact: {
      id: 'impact',
      name: t('impact'),
      ref: useRef<HTMLDivElement>(null),
    },
    context: {
      id: 'context',
      name: t('context'),
      ref: useRef<HTMLDivElement>(null),
    },
  };

  const scrollActiveId = useScrollSpy(Object.values(sections).map(({ id, ref }) => ({ id, ref })));

  const handleIntroScrollClick = () => {
    sections.services?.ref?.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const indicators = useMemo(() => {
    const indicators: { [key: string]: StaticIndicator } = {};

    Object.entries(STATIC_INDICATOR_MAPPING).map(([key, value]) => {
      const indicator = staticIndicators?.data?.find(
        ({ attributes }) => attributes.slug === value
      )?.attributes;

      if (!indicator) return;
      indicators[key] = indicator;
    });

    return indicators;
  }, [staticIndicators]);

  const protectedOceanPercentage = useMemo(() => {
    const protectionCoverageStatsData = protectionCoverageStats?.data;

    if (!protectionCoverageStatsData?.length) return null;

    return formatPercentage(locale, protectionCoverageStatsData[0].attributes.coverage, {
      displayPercentageSign: false,
    });
  }, [locale, protectionCoverageStats]);

  return (
    <Layout theme="dark" hideLogo={true} hero={<Intro onScrollClick={handleIntroScrollClick} />}>
      <Sidebar sections={sections} activeSection={scrollActiveId} arrowColor={'orange'} />
      <Content>
        <Section ref={sections.services.ref}>
          <SectionTitle>{t('section-services-title')}</SectionTitle>
          <SectionDescription>
            {t.rich('section-services-description', {
              b: (chunks) => <b>{chunks}</b>,
              i: (chunks) => <i>{chunks}</i>,
            })}
          </SectionDescription>
          <SectionContent>
            <LinkCards />
          </SectionContent>
        </Section>

        <Section ref={sections.impact.ref}>
          <SectionTitle>{t('section-impact-title')}</SectionTitle>

          <TwoColSubsection
            title={t('section-impact-subsection-1-title')}
            itemNum={1}
            itemTotal={3}
            description={
              <>
                <p>
                  {t.rich('section-impact-subsection-1-description-1', {
                    a1: (chunks) => (
                      <a
                        className="underline"
                        href={indicators?.biodiversityTextLand?.source}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {chunks}
                      </a>
                    ),
                    a2: (chunks) => (
                      <a
                        className="underline"
                        href={indicators?.biodiversity?.source}
                        target="_blank"
                        rel="noopener noreferrer"
                      >
                        {chunks}
                      </a>
                    ),
                    protectedOceanPercentage,
                    protectedLandPercentage: indicators?.biodiversityTextLand?.value,
                    threatenedSpeciesPercentage: indicators?.biodiversity?.value,
                  })}
                </p>
                <p className="mt-4 font-bold">{t('section-impact-subsection-1-description-2')}</p>
              </>
            }
          />

          <StatsImage
            value={indicators?.biodiversity?.value}
            description={indicators?.biodiversity?.description}
            sourceLink={indicators?.biodiversity?.source}
            image="stats1"
            valueSize="small"
          />

          <TwoColSubsection
            title={t('section-impact-subsection-2-title')}
            itemNum={2}
            itemTotal={3}
            description={
              <>
                <p>{t('section-impact-subsection-2-description-1')}</p>
                <p className="mt-4 font-bold">{t('section-impact-subsection-2-description-2')}</p>
              </>
            }
          />

          <StatsImage
            value={indicators?.climate?.value}
            description={indicators?.climate?.description}
            sourceLink={indicators?.climate?.source}
            image="stats2"
          />

          <TwoColSubsection
            title={t('section-impact-subsection-3-title')}
            itemNum={3}
            itemTotal={3}
            description={
              <>
                <p>{t('section-impact-subsection-3-description-1')}</p>
                <p className="mt-4 font-bold">{t('section-impact-subsection-3-description-2')}</p>
              </>
            }
          />

          <StatsImage
            value={indicators?.livesLivelihoods?.value}
            description={indicators?.livesLivelihoods?.description}
            sourceLink={indicators?.livesLivelihoods?.source}
            image="stats3"
          />
        </Section>

        <Section ref={sections.context.ref}>
          <SectionTitle>{t('section-context-title')}</SectionTitle>
          <SectionContent>
            <TwoColSubsection
              title={t('section-context-subsection-1-title')}
              description={t('section-context-subsection-1-description')}
            >
              <EarthSurfaceCoverage />
            </TwoColSubsection>
          </SectionContent>

          <TwoColSubsection
            title={t('section-context-subsection-2-title')}
            description={t('section-context-subsection-2-description')}
          />

          <SectionContent className="mt-10">
            <InteractiveMap />
          </SectionContent>
        </Section>
      </Content>
    </Layout>
  );
};

Home.messages = [
  'pages.home',
  ...Layout.messages,
  ...Intro.messages,
  ...LinkCards.messages,
  ...EarthSurfaceCoverage.messages,
];

export const getServerSideProps: GetServerSideProps = async (context) => {
  const queryClient = new QueryClient();

  const protectionCoverageStatsQueryParams = {
    locale: context.locale,
    filters: {
      location: {
        code: 'GLOB',
      },
      is_last_year: {
        $eq: true,
      },
      environment: {
        slug: {
          $eq: 'marine',
        },
      },
    },
    populate: '*',
    // eslint-disable-next-line @typescript-eslint/ban-ts-comment
    // @ts-ignore
    'sort[year]': 'desc',
    'pagination[limit]': 1,
  };

  await queryClient.prefetchQuery({
    ...getGetStaticIndicatorsQueryOptions({ locale: context.locale }),
  });

  await queryClient.prefetchQuery({
    ...getGetProtectionCoverageStatsQueryOptions(protectionCoverageStatsQueryParams),
  });

  const staticIndicatorsData = queryClient.getQueryData<StaticIndicatorListResponse>(
    getGetStaticIndicatorsQueryKey({ locale: context.locale })
  );

  const protectionCoverageStatsData = queryClient.getQueryData<ProtectionCoverageStatListResponse>(
    getGetProtectionCoverageStatsQueryKey(protectionCoverageStatsQueryParams)
  );

  return {
    props: {
      staticIndicators: staticIndicatorsData || { data: [] },
      protectionCoverageStats: protectionCoverageStatsData || { data: [] },
      dehydratedState: dehydrate(queryClient),
      messages: await fetchTranslations(context.locale, Home.messages),
    },
  };
};

export default Home;
