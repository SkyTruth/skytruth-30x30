import { useRouter } from 'next/router';

import { useLocale } from 'next-intl';

import { useSyncMapContentSettings } from '@/containers/map/sync-settings';
import { cn } from '@/lib/classnames';
import { FCWithMessages } from '@/types';
import { useGetLocations } from '@/types/generated/location';

import FishingProtectionWidget from './fishing-protection';
import HabitatWidget from './habitat';
import MarineConservationWidget from './marine-conservation';
import ProtectionTypesWidget from './protection-types';

const MarineWidgets: FCWithMessages = () => {
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
      <MarineConservationWidget location={locationData} />
      <ProtectionTypesWidget location={locationData.code} />
      <FishingProtectionWidget location={locationData.code} />
      <HabitatWidget location={locationData.code} />
    </div>
  );
};

MarineWidgets.messages = [
  ...MarineConservationWidget.messages,
  ...ProtectionTypesWidget.messages,
  ...FishingProtectionWidget.messages,
  ...HabitatWidget.messages,
];

export default MarineWidgets;
