import { useMemo } from 'react';

import { groupBy } from 'lodash-es';

import HorizontalBarChart from '@/components/charts/horizontal-bar-chart';
import Widget from '@/components/widget';
import { ESTABLISHMENT_STAGES_CHART_BAR_BACKGROUNDS } from '@/constants/establishment-stages-chart-bar-backgrounds';
import { useGetMpaaEstablishmentStageStats } from '@/types/generated/mpaa-establishment-stage-stat';
import type { Location } from '@/types/generated/strapi.schemas';

type EstablishmentStagesWidgetProps = {
  location: Location;
};

const EstablishmentStagesWidget: React.FC<EstablishmentStagesWidgetProps> = ({ location }) => {
  // Default params: filter by location
  const defaultQueryParams = {
    filters: {
      location: {
        code: location.code,
      },
    },
  };

  // Find last updated in order to display the last data update
  const { data: dataLastUpdate } = useGetMpaaEstablishmentStageStats(
    {
      ...defaultQueryParams,
      sort: 'updatedAt:desc',
      'pagination[limit]': 1,
    },
    {
      query: {
        select: ({ data }) => data?.[0]?.attributes?.updatedAt,
        placeholderData: { data: null },
      },
    }
  );

  // Get establishment stages by location
  const {
    data: { data: establishmentStagesData },
  } = useGetMpaaEstablishmentStageStats(
    {
      ...defaultQueryParams,
      populate: '*',
      'pagination[limit]': -1,
    },
    {
      query: {
        select: ({ data }) => ({ data }),
        placeholderData: { data: [] },
      },
    }
  );

  // Merge OECM and MPA stats
  const mergedEstablishmentStagesStats = useMemo(() => {
    if (!establishmentStagesData.length) return [];

    const groupedByStage = groupBy(
      establishmentStagesData,
      'attributes.mpaa_establishment_stage.data.attributes.slug'
    );

    return Object.keys(groupedByStage).map((establishmentStage) => {
      const entries = groupedByStage[establishmentStage];
      const totalArea = entries.reduce((acc, entry) => acc + entry.attributes.area, 0);
      const establishmentStageData =
        groupedByStage[establishmentStage]?.[0]?.attributes?.mpaa_establishment_stage?.data
          ?.attributes;

      return {
        slug: establishmentStageData.slug,
        name: establishmentStageData.name,
        info: establishmentStageData.info,
        area: totalArea,
      };
    });
  }, [establishmentStagesData]);

  // Parse data to display in the chart
  const widgetChartData = useMemo(() => {
    if (!mergedEstablishmentStagesStats.length) return [];

    const parsedData = mergedEstablishmentStagesStats.map((establishmentStage) => {
      return {
        title: establishmentStage.name,
        slug: establishmentStage.slug,
        barBackground: ESTABLISHMENT_STAGES_CHART_BAR_BACKGROUNDS[establishmentStage.slug],
        totalArea: location.totalMarineArea,
        protectedArea: establishmentStage.area,
        info: establishmentStage.info,
      };
    });

    return parsedData;
  }, [location, mergedEstablishmentStagesStats]);

  // If there's no widget data, don't display the widget
  if (!widgetChartData.length) return null;

  return (
    <Widget title="Marine Conservation Establishment Stages" lastUpdated={dataLastUpdate}>
      {widgetChartData.map((chartData) => (
        <HorizontalBarChart key={chartData.slug} className="py-2" data={chartData} />
      ))}
    </Widget>
  );
};

export default EstablishmentStagesWidget;
