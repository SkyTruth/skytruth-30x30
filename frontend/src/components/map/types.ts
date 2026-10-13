import type { ComponentPropsWithoutRef } from 'react';

import type { Map, ViewState } from 'react-map-gl';

import { FitBoundsOptions } from 'mapbox-gl';

// react-map-gl's `MapProps` alias follows the installed mapbox-gl typings, but
// the `Map` component's prop type is fixed at react-map-gl's build; they differ.
export interface CustomMapProps extends Omit<ComponentPropsWithoutRef<typeof Map>, 'projection'> {
  id?: string;
  /** A function that returns the map instance */
  children?: React.ReactNode;

  /** Custom css class for styling */
  className?: string;

  /** An string that defines the rotation axis */
  constrainedAxis?: 'x' | 'y';

  /** An object that defines the bounds */
  bounds?: {
    bbox: readonly [number, number, number, number];
    options?: FitBoundsOptions;
    viewportOptions?: Partial<ViewState>;
  };

  /** A function that exposes the viewport */
  onMapViewStateChange?: (viewstate: Partial<ViewState>) => void;
}
