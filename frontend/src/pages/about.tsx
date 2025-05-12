import { useMemo, useRef } from 'react';

import { QueryClient, dehydrate } from '@tanstack/react-query';
import { GetServerSideProps } from 'next';
import { useTranslations } from 'next-intl';

import Intro from '@/components/static-pages/intro';
import Section, {
  SectionTitle,
  SectionDescription,
  SectionContent,
} from '@/components/static-pages/section';
import StatsImage from '@/components/static-pages/stats-image';
import SubSection, {
  SubSectionContent,
  SubSectionTitle,
} from '@/components/static-pages/sub-section';
import TwoColSubsection from '@/components/static-pages/two-col-subsection';
import HighlightedText from '@/containers/about/highlighted-text';
import Logo from '@/containers/about/logo';
import LogosGrid from '@/containers/about/logos-grid';
import QuestionsList from '@/containers/about/questions-list';
import useScrollSpy from '@/hooks/use-scroll-spy';
import Layout, { Sidebar, Content } from '@/layouts/static-page';
import { fetchTranslations } from '@/lib/i18n';
import { FCWithMessages } from '@/types';
import {
  getGetStaticIndicatorsQueryKey,
  getGetStaticIndicatorsQueryOptions,
} from '@/types/generated/static-indicator';
import { StaticIndicator, StaticIndicatorListResponse } from '@/types/generated/strapi.schemas';

const About: FCWithMessages = ({
  staticIndicators,
}: {
  staticIndicators: StaticIndicatorListResponse;
}) => {
  const t = useTranslations('pages.about');

  const sections = {
    definition: {
      id: 'definition',
      name: t('definition'),
      ref: useRef<HTMLDivElement>(null),
    },
    problem: {
      id: 'problem',
      name: t('problem'),
      ref: useRef<HTMLDivElement>(null),
    },
    dataPartners: {
      id: 'data-partners',
      name: t('data-partners'),
      ref: useRef<HTMLDivElement>(null),
    },
    futureObjectives: {
      id: 'future-objectives',
      name: t('future-objectives'),
      ref: useRef<HTMLDivElement>(null),
    },
    teamAndFunders: {
      id: 'teams-and-funders',
      name: t('team-and-funders'),
      ref: useRef<HTMLDivElement>(null),
    },
  };

  const scrollActiveId = useScrollSpy(Object.values(sections).map(({ id, ref }) => ({ id, ref })));

  const handleIntroScrollClick = () => {
    sections.definition?.ref?.current?.scrollIntoView({ behavior: 'smooth' });
  };

  const protectedWatersIndicator: StaticIndicator = useMemo(() => {
    return staticIndicators?.data?.find(
      ({ attributes }) => attributes.slug === 'terrestrial-inland-areas-protected'
    )?.attributes;
  }, [staticIndicators]);

  return (
    <Layout
      title={t('page-title')}
      hero={
        <Intro
          title={t('intro-title')}
          color="purple"
          image="tablet"
          onScrollClick={handleIntroScrollClick}
        />
      }
    >
      <Sidebar sections={sections} activeSection={scrollActiveId} arrowColor="purple" />
      <Content>
        <Section ref={sections.definition.ref}>
          <SectionTitle>{t('section-definition-title')}</SectionTitle>
          <SectionDescription>
            {t.rich('section-definition-description', {
              b: (chunks) => <b>{chunks}</b>,
              a: (chunks) => (
                <a
                  className="underline"
                  href="https://www.nytimes.com/2022/12/19/climate/biodiversity-cop15-montreal-30x30.html"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {chunks}
                </a>
              ),
            })}
          </SectionDescription>
        </Section>
        <Section ref={sections.problem.ref}>
          <SectionTitle>{t('section-problem-title')}</SectionTitle>
          <SectionDescription>
            <p>{t('section-problem-description-1')}</p>
            <p className="mt-4 font-bold">{t('section-problem-description-2')}</p>
          </SectionDescription>

          <SectionContent>
            <HighlightedText>
              {t.rich('section-highlighted-1-title', {
                b: (chunks) => <span className="text-black">{chunks}</span>,
              })}
            </HighlightedText>
            <QuestionsList
              questions={[
                t('section-highlighted-1-question-1'),
                t('section-highlighted-1-question-2'),
                t('section-highlighted-1-question-3'),
              ]}
            />
          </SectionContent>
        </Section>
        <Section ref={sections.dataPartners.ref}>
          <SectionTitle>{t('section-data-partners-title')}</SectionTitle>
          <SectionDescription>{t('section-data-partners-description')}</SectionDescription>

          <SectionContent>
            <TwoColSubsection
              itemNum={1}
              itemTotal={3}
              title={t('section-wdpa-title')}
              description={t.rich('section-wdpa-description', {
                a: (chunks) => (
                  <a
                    href="https://www.protectedplanet.net"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <u>{chunks}</u>
                  </a>
                ),
              })}
            >
              <Logo logo="protectedPlanet" />
            </TwoColSubsection>
          </SectionContent>

          <SectionContent>
            <TwoColSubsection
              itemNum={2}
              itemTotal={3}
              title={t('section-mpatlas-title')}
              description={t.rich('section-mpatlas-description', {
                a: (chunks) => (
                  <a href="https://mpatlas.org" target="_blank" rel="noopener noreferrer">
                    <u>{chunks}</u>
                  </a>
                ),
              })}
            >
              <Logo logo="marineProtectionAtlas" />
            </TwoColSubsection>
          </SectionContent>

          <SectionContent>
            <TwoColSubsection
              itemNum={3}
              itemTotal={3}
              title={t('section-protectedseas-title')}
              description={t.rich('section-protectedseas-description', {
                a: (chunks) => (
                  <a href="https://protectedseas.net" target="_blank" rel="noopener noreferrer">
                    <u>{chunks}</u>
                  </a>
                ),
              })}
            >
              <Logo logo="protectedSeas" />
            </TwoColSubsection>
          </SectionContent>
        </Section>
        <Section ref={sections.futureObjectives.ref}>
          <SectionTitle>{t('section-future-objectives-title')}</SectionTitle>
          <SectionDescription>
            {t.rich('section-future-objectives-description', {
              a: (chunks) => (
                <a
                  href="https://www.bloomberg.org/environment/protecting-the-oceans/bloomberg-ocean/"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  <u>{chunks}</u>
                </a>
              ),
            })}
          </SectionDescription>

          <SectionContent>
            <HighlightedText>
              {t.rich('section-highlighted-2-title', {
                b: (chunks) => <span className="text-black">{chunks}</span>,
              })}
            </HighlightedText>
            <HighlightedText>
              {t.rich('section-highlighted-2-description', {
                b: (chunks) => <span className="text-black">{chunks}</span>,
              })}
            </HighlightedText>
          </SectionContent>

          <StatsImage
            value={protectedWatersIndicator?.value}
            description={protectedWatersIndicator?.description}
            sourceLink={protectedWatersIndicator?.source}
            image="stats4"
            color="purple"
          />
        </Section>
        <Section ref={sections.teamAndFunders.ref}>
          <SectionTitle>{t('section-team-and-funders-title')}</SectionTitle>
          <SectionDescription>{t('section-team-and-funders-description')}</SectionDescription>

          <SubSection borderTop={true}>
            <SubSectionTitle>{t('section-team-title')}</SubSectionTitle>
            <SubSectionContent className="justify-left">
              <LogosGrid className="md:mt-8" type="team" columns={4} />
            </SubSectionContent>
          </SubSection>

          <SubSection borderTop={true}>
            <SubSectionTitle>{t('section-funders-title')}</SubSectionTitle>
            <SubSectionContent className="justify-left">
              <LogosGrid className="justify-left md:mt-8" type="funders" columns={2} />
            </SubSectionContent>
          </SubSection>
        </Section>
      </Content>
    </Layout>
  );
};

About.messages = ['pages.about', ...Layout.messages, ...LogosGrid.messages];

export const getServerSideProps: GetServerSideProps = async (context) => {
  const queryClient = new QueryClient();

  await queryClient.prefetchQuery({
    ...getGetStaticIndicatorsQueryOptions({
      locale: context.locale,
    }),
  });

  const staticIndicatorsData = queryClient.getQueryData<StaticIndicatorListResponse>(
    getGetStaticIndicatorsQueryKey({
      locale: context.locale,
    })
  );

  return {
    props: {
      staticIndicators: staticIndicatorsData || { data: [] },
      dehydratedState: dehydrate(queryClient),
      messages: await fetchTranslations(context.locale, About.messages),
    },
  };
};

export default About;
