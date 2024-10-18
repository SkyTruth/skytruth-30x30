import { ComponentProps, PropsWithChildren, ReactNode, useMemo } from 'react';

import { timeFormatLocale } from 'd3-time-format';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import en from 'd3-time-format/locale/en-US';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import es from 'd3-time-format/locale/es-ES';
// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-ignore
import fr from 'd3-time-format/locale/fr-FR';
import { useLocale, useTranslations } from 'next-intl';

import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

import TooltipButton from '../tooltip-button';

import Loading from './loading';
import NoData from './no-data';

type WidgetProps = {
  className?: string;
  title?: string;
  lastUpdated?: string;
  noData?: boolean;
  noDataMessage?: ComponentProps<typeof NoData>['message'];
  loading?: boolean;
  error?: boolean;
  errorMessage?: ComponentProps<typeof NoData>['message'];
  info?: ComponentProps<typeof TooltipButton>['text'];
  sources?: ComponentProps<typeof TooltipButton>['sources'];
  tooltipExtraContent?: ReactNode;
};

const d3Locales = {
  en,
  es,
  fr,
};

const Widget: FCWithMessages<PropsWithChildren<WidgetProps>> = ({
  className,
  title,
  lastUpdated,
  noData = false,
  noDataMessage = undefined,
  loading = false,
  error = false,
  errorMessage = undefined,
  info,
  sources,
  tooltipExtraContent,
  children,
}) => {
  const t = useTranslations('components.widget');
  const locale = useLocale();

  const d3Locale = useMemo(() => timeFormatLocale(d3Locales[locale]), [locale]);

  const formattedLastUpdated = useMemo(
    () => d3Locale.format('%B %Y')(new Date(lastUpdated)),
    [lastUpdated, d3Locale]
  );

  const showNoData = !loading && (noData || error);

  return (
    <div className={cn('py-4 px-4 md:px-8', className)}>
      <div className="pt-2">
        <span className="flex items-baseline justify-between">
          {title && <h2 className="font-sans text-xl font-bold leading-tight">{title}</h2>}
          {(info || sources) && (
            <TooltipButton text={info} sources={sources} extraContent={tooltipExtraContent} />
          )}
        </span>
        {!showNoData && lastUpdated && (
          <span className="text-xs">{t('updated-on', { date: formattedLastUpdated })}</span>
        )}
      </div>
      {loading && <Loading />}
      {!loading && error && <NoData error={error} message={errorMessage} />}
      {!loading && !error && noData && <NoData error={error} message={noDataMessage} />}
      {!loading && !error && !noData && <div>{children}</div>}
    </div>
  );
};

Widget.messages = ['components.widget', ...Loading.messages, ...NoData.messages];

export default Widget;
