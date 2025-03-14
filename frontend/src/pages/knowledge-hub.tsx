import { useRef } from 'react';

import dynamic from 'next/dynamic';

import { GetServerSideProps } from 'next';
import { useTranslations } from 'next-intl';

import MobileDisclaimerDialogStatic from '@/components/mobile-disclaimer-dialog';
import Intro from '@/components/static-pages/intro';
import Section from '@/components/static-pages/section';
import CardFilters from '@/containers/knowledge-hub/card-filters';
import CardList from '@/containers/knowledge-hub/card-list';
import Layout, { Content } from '@/layouts/static-page';
import { fetchTranslations } from '@/lib/i18n';
import { FCWithMessages } from '@/types';

const MobileDisclaimerDialog = dynamic(() => import('@/components/mobile-disclaimer-dialog'), {
  ssr: false,
});

const KnowledgeHubPage: FCWithMessages = () => {
  const t = useTranslations('pages.knowledge-hub');

  const sectionRef = useRef<HTMLDivElement>(null);

  const handleIntroScrollClick = () => {
    sectionRef?.current?.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <Layout
      title={t('page-title')}
      hero={
        <Intro
          title={t('intro-title')}
          description={t('intro-description')}
          color="green"
          image="magnifyingGlass"
          onScrollClick={handleIntroScrollClick}
        />
      }
    >
      <MobileDisclaimerDialog />
      <Content>
        <Section ref={sectionRef} borderTop={false} className="py-0 md:mb-0">
          <div className="space-y-24">
            <h2 className="text-[52px] font-black leading-none">{t('looking-for')}</h2>
            <div className="space-y-4">
              <CardFilters />
              <CardList />
            </div>
          </div>
        </Section>
      </Content>
    </Layout>
  );
};

KnowledgeHubPage.messages = [
  'pages.knowledge-hub',
  ...Layout.messages,
  ...CardFilters.messages,
  ...CardList.messages,
  ...MobileDisclaimerDialogStatic.messages,
];

export const getServerSideProps: GetServerSideProps = async (context) => {
  return {
    props: {
      messages: await fetchTranslations(context.locale, KnowledgeHubPage.messages),
    },
  };
};

export default KnowledgeHubPage;
