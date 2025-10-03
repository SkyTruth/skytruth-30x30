import { useEffect, useMemo, useRef, useState } from 'react';

import twTheme from 'lib/tailwind';

import { maxBy } from 'lodash-es';
import { useTranslations } from 'next-intl';
import {
  ComposedChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
  Tooltip,
  ReferenceLine,
  Line,
} from 'recharts';

import TooltipButton from '@/components/tooltip-button';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';

import { getMultilineRenderer } from './helpers';
import ChartLegend from './legend';
import ChartTooltip from './tooltip';

type ConservationChartProps = {
  className?: string;
  displayTarget?: boolean;
  target?: number;
  targetYear?: number;
  tooltipSlug: string;
  data: {
    year?: number;
    percentage: number;
    protectedArea: number;
    totalArea: number;
    active?: boolean;
    future?: boolean;
  }[];
};

const TARGET_YEAR = 2030;
const MAX_NUM_YEARS = 20;

const ConservationChart: FCWithMessages<ConservationChartProps> = ({
  className,
  displayTarget = true,
  target = 30,
  targetYear = 2030,
  tooltipSlug,
  data,
}) => {
  const t = useTranslations('components.chart-conservation');

  const [chartReady, setChartReady] = useState(false);
  const maxRecord = useMemo(() => maxBy(data, (data) => data.percentage), [data]);
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const chartContainer = chartRef.current;
    if (!chartContainer) return;

    const isParentReady = () => {
      const width = chartContainer.clientWidth;
      const height = chartContainer.clientHeight;
      setChartReady(width > 0 && height > 0);
    };

    isParentReady();
    const observer = new ResizeObserver(isParentReady);
    observer.observe(chartContainer);
    return () => observer.disconnect();
  }, []);

  const barChartData = useMemo(() => {
    // Last year of data available
    const lastEntryYear = data[data.length - 1]?.year;

    // Add bogus values from the last year to the target year (2030) to the array, so that the chart
    // displays years from the beginning of the historical data, until the target year (projection).
    const missingYearsArr = [...Array(TARGET_YEAR - lastEntryYear).keys()].map(
      (i) => i + lastEntryYear + 1
    );

    const missingYearsData = missingYearsArr.map((year) => {
      return {
        percentage: null,
        year: year,
        active: false,
        totalArea: null,
        protectedArea: null,
        future: true,
      };
    });

    // Cap results to the least 20 entries, or chart will be too big
    return [...data, ...missingYearsData].slice(-20);
  }, [data]);

  // Not using useMemo as it may not be worth the overhead, performance wise
  const firstYearData = barChartData[0];
  const lastYearData = barChartData[barChartData?.length - 1];
  const activeYearData = barChartData.find(({ active }) => active);
  const xAxisTicks = [firstYearData?.year, activeYearData?.year, lastYearData?.year];
  const numHistoricalYears = activeYearData?.year - firstYearData?.year;
  const historicalDelta =
    (activeYearData?.percentage - firstYearData?.percentage) / numHistoricalYears;

  // Calculate data for the historical line; first and active year are known, years in between
  // need to be extrapolated.
  const historicalLineData = useMemo(() => {
    if (Number.isNaN(historicalDelta)) {
      return [];
    }
    const missingYearsArr =
      activeYearData.year === firstYearData.year
        ? []
        : [...Array(activeYearData.year - firstYearData.year - 1).keys()].map(
            (i) => i + firstYearData.year + 1
          );

    const extrapolatedHistoricalYears = missingYearsArr.map((year, idx) => {
      return {
        year,
        percentage: firstYearData.percentage + historicalDelta * (idx + 1),
      };
    });

    return [
      { year: firstYearData.year, percentage: firstYearData.percentage },
      ...extrapolatedHistoricalYears,
      {
        year: activeYearData.year,
        percentage: activeYearData.percentage,
      },
    ];
  }, [activeYearData, firstYearData, historicalDelta]);

  // Calculate data for the projected line; we know the active and target years; extrapolate
  // the projection based on the historical data.
  const projectedLineData = useMemo(() => {
    if (Number.isNaN(historicalDelta)) {
      return [];
    }
    const yearsArray = [...Array(TARGET_YEAR - activeYearData.year).keys()].map(
      (i) => i + activeYearData.year + 1
    );

    const extrapolatedProjectedYears = yearsArray.map((year, idx) => {
      const value = activeYearData.percentage + historicalDelta * (idx + 1);
      return {
        year,
        percentage: value <= 100 ? value : 100,
      };
    });

    return [
      { year: activeYearData.year, percentage: activeYearData.percentage },
      ...extrapolatedProjectedYears,
    ];
  }, [activeYearData, historicalDelta]);

  const chartData = useMemo(() => {
    const historicalYearsArray = data?.map(({ year }) => year);
    const lastDataYear = historicalYearsArray[historicalYearsArray.length - 1];
    const futureYearsArray = [...Array(TARGET_YEAR - lastDataYear).keys()].map(
      (i) => i + lastDataYear + 1
    );
    const allYearsArray = [...historicalYearsArray, ...futureYearsArray];

    return allYearsArray
      .map((year) => {
        const percentage = data?.find(({ year: dataYear }) => year === dataYear)?.percentage;
        const historical = historicalLineData?.find(
          ({ year: historicalYear }) => year === historicalYear
        )?.percentage;
        const projected = projectedLineData?.find(
          ({ year: projectedYear }) => year === projectedYear
        )?.percentage;

        return {
          year,
          percentage,
          historical,
          projected,
          active: year === lastDataYear,
        };
      })
      ?.slice(-MAX_NUM_YEARS);
  }, [data, historicalLineData, projectedLineData]);

  return (
    <div className={cn(className, 'text-xs text-black')} ref={chartRef}>
      {chartReady && (
        <ResponsiveContainer width="100%" height="100%" minWidth={1} minHeight={1}>
          <ComposedChart data={chartData}>
            <CartesianGrid vertical={false} strokeDasharray="3 3" />
            {firstYearData?.year !== activeYearData?.year ? (
              <>
                <ReferenceLine
                  xAxisId={1}
                  x={firstYearData.year - 0.4}
                  label={{ position: 'insideTopLeft', value: t('historical'), fill: '#000' }}
                  stroke="#000"
                  strokeWidth={0}
                />
                <ReferenceLine
                  xAxisId={1}
                  x={activeYearData.year + 0.4}
                  label={getMultilineRenderer(t('future-projection'), 15)}
                  stroke="#000"
                />
              </>
            ) : null}
            <XAxis
              xAxisId={1}
              type="number"
              dataKey="year"
              ticks={xAxisTicks}
              domain={[firstYearData.year - 0.4, lastYearData.year + 0.4]}
              stroke="#000"
              tick={{ fill: '#000' }}
              axisLine={{ stroke: '#000' }}
              tickLine={{ stroke: '#000' }}
            />
            <Bar dataKey="percentage" xAxisId={1}>
              {chartData.map((entry, index) => (
                <Cell
                  stroke="black"
                  fill={entry?.active ? 'black' : 'transparent'}
                  key={`cell-${index}`}
                />
              ))}
            </Bar>
            <Line
              xAxisId={2}
              type="monotone"
              strokeWidth={4}
              dataKey="historical"
              stroke={twTheme.colors.white as string}
              dot={false}
              activeDot={false}
            />
            <Line
              xAxisId={2}
              type="monotone"
              strokeWidth={4}
              dataKey="projected"
              stroke={twTheme.colors.white as string}
              dot={false}
              activeDot={false}
            />
            <Line
              xAxisId={2}
              type="monotone"
              strokeWidth={1}
              dataKey="historical"
              stroke={twTheme.colors.violet as string}
              dot={false}
              activeDot={false}
            />
            <Line
              xAxisId={2}
              type="monotone"
              strokeWidth={1}
              strokeDasharray="4 4"
              dataKey="projected"
              stroke={twTheme.colors.violet as string}
              dot={false}
              activeDot={false}
            />
            {displayTarget && (
              <>
                <ReferenceLine
                  xAxisId={1}
                  y={target}
                  strokeWidth={4}
                  stroke={twTheme.colors.white as string}
                />
                <ReferenceLine xAxisId={1} y={target} stroke="#FD8E28" strokeDasharray="3 3" />
              </>
            )}
            <XAxis
              xAxisId={2}
              type="number"
              dataKey="year"
              hide={true}
              domain={[firstYearData.year, lastYearData.year]}
            />
            <YAxis
              domain={maxRecord.percentage < 55 ? [0, 55] : [0, 100]}
              ticks={
                maxRecord.percentage < 55 ? [0, 15, 30, 45, 55] : [0, 15, 30, 45, 60, 75, 90, 100]
              }
              tickFormatter={(value) => `${value}%`}
              stroke="#000"
              tick={{ fill: '#000' }}
              axisLine={{ stroke: '#000' }}
              tickLine={{ stroke: '#000' }}
            />
            <Tooltip content={ChartTooltip} />
          </ComposedChart>
        </ResponsiveContainer>
      )}
      <ChartLegend
        displayTarget={displayTarget}
        target={target}
        targetYear={targetYear}
        tooltipSlug={tooltipSlug}
        displayProjections={numHistoricalYears > 0}
      />
    </div>
  );
};

ConservationChart.messages = [
  'components.chart-conservation',
  ...TooltipButton.messages,
  ...ChartLegend.messages,
  ...ChartTooltip.messages,
];

export default ConservationChart;
