export const MAX_PERCENTAGE = 100;

// Width of a bar segment, capped at the full bar
export const toWidth = (percentage: number) => `${Math.min(percentage, MAX_PERCENTAGE)}%`;
