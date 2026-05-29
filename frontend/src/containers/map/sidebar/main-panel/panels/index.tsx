import { useAtom } from 'jotai';

import { mapTypeAtom } from '@/containers/map/store';
import { FCWithMessages } from '@/types';
import { MapTypes } from '@/types/map';

import Details from './details';
import Modelling from './modelling';

const SIDEBAR_COMPONENTS = {
  [MapTypes.ProgressTracker]: Details,
  [MapTypes.ConservationBuilder]: Modelling,
};

const MainPanel: FCWithMessages = () => {
  const [mapType] = useAtom(mapTypeAtom);

  const Component = SIDEBAR_COMPONENTS[mapType] || Details;

  return <Component />;
};

MainPanel.messages = [...Details.messages, ...Modelling.messages];

export default MainPanel;
