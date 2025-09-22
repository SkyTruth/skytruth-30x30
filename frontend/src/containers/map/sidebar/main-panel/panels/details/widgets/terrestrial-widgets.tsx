import { useRouter } from 'next/router';

import { useLocale } from 'next-intl';

import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { useGetLocations } from '@/types/generated/location';

import HabitatWidget from './habitat';
import TerrestrialConservationWidget from './terrestrial-conservation';

const TerrestrialWidgets: FCWithMessages = () => {
  const locale = useLocale();

  const {
    query: { locationCode = 'GLOB' },
  } = useRouter();

  const [{ showDetails }] = useSyncMapContentSettings();

  const { data: locationData } = useGetLocations(
    {
      locale,
      filters: {
        code: locationCode,
      },
      'pagination[limit]': 1,
    },
    {
      query: {
        select: ({ data }) => data[0]?.attributes ?? null,
      },
    }
  );

  if (!locationData) {
    return null;
  }

  return (
    <div
      className={cn({
        'flex flex-col divide-y-[1px] divide-black font-mono': true,
        'pb-40': showDetails,
      })}
    >
      <TerrestrialConservationWidget location={locationData} />
      <HabitatWidget location={locationData.code} />
    </div>
  );
};

TerrestrialWidgets.messages = [...TerrestrialConservationWidget.messages];

export default TerrestrialWidgets;
