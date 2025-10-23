import { ComponentProps, PropsWithChildren, ReactNode, useMemo } from 'react';

import { timeFormatLocale } from 'd3-time-format';
// @ts-ignore
import en from 'd3-time-format/locale/en-US';
// @ts-ignore
import es from 'd3-time-format/locale/es-ES';
// @ts-ignore
import fr from 'd3-time-format/locale/fr-FR';
// @ts-ignore
import pt from 'd3-time-format/locale/pt-BR';
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
  noDataClassName?: string;
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
  pt,
};

const Widget: FCWithMessages<PropsWithChildren<WidgetProps>> = ({
  className,
  title,
  lastUpdated,
  noData = false,
  noDataMessage = undefined,
  noDataClassName,
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
  const validSources = Array.isArray(sources) ? sources.length > 0 : !!sources;

  return (
    <div className={cn('px-4 py-4 md:px-8', className)}>
      <div className="pt-2">
        <span className="flex items-baseline justify-between">
          {title && <h2 className="font-sans text-xl font-bold leading-tight">{title}</h2>}
          {(info || sources) && (
            <TooltipButton
              text={info}
              sources={validSources && sources}
              extraContent={tooltipExtraContent}
            />
          )}
        </span>
        {!showNoData && lastUpdated && (
          <span className="text-xs">{t('updated-on', { date: formattedLastUpdated })}</span>
        )}
      </div>
      {loading && <Loading />}
      {!loading && error && (
        <NoData error={error} message={errorMessage} className={noDataClassName} />
      )}
      {!loading && !error && noData && (
        <NoData error={error} message={noDataMessage} className={noDataClassName} />
      )}
      {!loading && !error && !noData && <div>{children}</div>}
    </div>
  );
};

Widget.messages = ['components.widget', ...Loading.messages, ...NoData.messages];

export default Widget;
