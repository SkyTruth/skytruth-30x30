import Image from 'next/image';

import { useLocale, useTranslations } from 'next-intl';

import Icon from '@/components/ui/icon';
import SidebarItem from '@/containers/homepage/intro/sidebar-item';
import { formatPercentage } from '@/lib/utils/formats';
import ArrowRight from '@/styles/icons/arrow-right.svg';
import { FCWithMessages } from '@/types';
import { useGetProtectionCoverageStats } from '@/types/generated/protection-coverage-stat';

type IntroProps = {
  onScrollClick: () => void;
};

const Intro: FCWithMessages<IntroProps> = ({ onScrollClick }) => {
  const t = useTranslations('containers.homepage-intro');
  const locale = useLocale();

  const { data: protectionStatsData } = useGetProtectionCoverageStats<{
    marine?: string;
    terrestrial?: string;
  }>(
    {
      locale,
      filters: {
        location: {
          code: 'GLOB',
        },
        is_last_year: {
          $eq: true,
        },
      },
      populate: 'location,environment',
      // eslint-disable-next-line @typescript-eslint/ban-ts-comment
      // @ts-ignore
      'sort[year]': 'desc',
    },
    {
      query: {
        placeholderData: { terrestrial: '−', marine: '−' },
        select: ({ data }) => {
          const terrestrialCoverage = data?.find(
            (d) => d.attributes.environment.data.attributes.slug === 'terrestrial'
          )?.attributes.coverage;

          const marineCoverage = data?.find(
            (d) => d.attributes.environment.data.attributes.slug === 'marine'
          )?.attributes.coverage;

          return {
            terrestrial:
              terrestrialCoverage !== undefined
                ? formatPercentage(locale, terrestrialCoverage, {
                    displayPercentageSign: false,
                  })
                : '−',
            marine:
              marineCoverage !== undefined
                ? formatPercentage(locale, marineCoverage, {
                    displayPercentageSign: false,
                  })
                : '−',
          };
        },
      },
    }
  );

  return (
    <div className="bg-black">
      <div className="flex flex-col text-white md:mx-auto md:max-w-7xl md:flex-row">
        <div className="mb-2 mt-6 flex flex-1 flex-col gap-10 px-8 pt-10">
          <div className="relative">
            <Image
              className="h-auto w-full max-w-4xl"
              src="/images/homepage/intro-30x30.svg"
              alt="SkyTruth 30x30"
              width="0"
              height="0"
              sizes="100vw"
            />
          </div>
          <div className="pr-10 text-5xl font-extrabold leading-tight md:text-6xl">
            {t('protect-land-and-ocean')}
          </div>
          <div className="mt-16 flex">
            <div className="mb-6 flex flex-grow items-center gap-4 text-xs">
              <span>
                <Image
                  src="/images/static-pages/logos/skytruth-white.png"
                  alt="SkyTruth 30x30"
                  width={57}
                  height={39}
                />
              </span>
              <span className="flex items-center gap-1.5">
                <span>{t('product-powered-by')}</span>
                <Image
                  src="/images/static-pages/logos/bloomberg-white.png"
                  alt="Bloomberg Philanthropies Ocean Initiative"
                  width={247}
                  height={29}
                />
              </span>
            </div>
          </div>
        </div>
        <div className="border-l border-t border-white md:w-[40%] md:border-t-0">
          <div className="flex h-full flex-col border-r">
            <SidebarItem
              percentage={protectionStatsData.marine}
              text={t('current-ocean-protected-area')}
              icon="icon1"
            />
            <SidebarItem
              percentage={protectionStatsData.terrestrial}
              text={t('current-total-protected-area')}
              icon="icon2"
            />
            <div className="flex h-full w-full justify-center">
              <button
                type="button"
                className="my-6 flex aspect-square min-h-[140px] items-center justify-center md:w-auto"
                onClick={onScrollClick}
              >
                <Icon icon={ArrowRight} className="h-[60%] rotate-90 fill-black" />
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

Intro.messages = ['containers.homepage-intro', ...SidebarItem.messages];

export default Intro;
