/**
 * Design tokens — "Mint & Moss" (Sentinel Playful Professional).
 *
 * Ported directly from the Stitch design spec (docs: DESIGN.md). This is the
 * single source of truth for colors, radii, and spacing across the app.
 */

export const colors = {
  // Surfaces
  surface: '#f9faf2', // page background (cream)
  surfaceBright: '#f9faf2',
  surfaceDim: '#d9dbd3',
  card: '#ffffff', // surface-container-lowest
  cardLow: '#f3f4ec',
  cardMuted: '#edefe7', // surface-container
  cardHigh: '#e8e9e1',
  cardHighest: '#e2e3db',

  // Text
  onSurface: '#1a1c18',
  onSurfaceVariant: '#404943',
  outline: '#707973',
  outlineVariant: '#bfc9c1',
  inverseSurface: '#2f312c',
  inverseOnSurface: '#f0f1e9',

  // Brand green (primary)
  primary: '#0f5238',
  primaryContainer: '#2d6a4f',
  onPrimary: '#ffffff',
  onPrimaryContainer: '#a8e7c5',
  primaryFixed: '#b1f0ce',
  primaryFixedDim: '#95d4b3',

  // Secondary / mint
  secondary: '#2b694d',
  secondaryContainer: '#b0f1cc',
  onSecondaryContainer: '#327053',
  vibrantMint: '#B7E4C7',

  // Semantic accents (reserved for urgency tiers / states)
  escalation: '#F43F5E', // rose — critical
  warning: '#F59E0B', // amber — aging urgency
  success: '#10B981', // emerald — approved/sent
  actionIndigo: '#6366F1', // indigo secondary action
  error: '#ba1a1a',
  onError: '#ffffff',
  errorContainer: '#ffdad6',

  // Channel brand colors (low-sat bg + high-sat text handled per component)
  discord: '#5865F2',
  discordSoft: '#E7E9FD',
  gmail: '#EA4335',
  gmailSoft: '#FCE4E2',

  // Utility
  white: '#ffffff',
  black: '#000000',
  transparent: 'transparent',
} as const;

export const radius = {
  sm: 8,
  md: 16,
  lg: 24,
  xl: 32,
  xxl: 40,
  full: 9999,
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  base: 16,
  lg: 20,
  xl: 24,
  xxl: 32,
  xxxl: 40,
  page: 24, // safe-area page margin
  card: 16, // internal card gutter
} as const;

/** Soft, large-radius ambient shadow tinted toward the brand green. */
export const shadow = {
  card: {
    shadowColor: '#0f5238',
    shadowOffset: { width: 0, height: 8 },
    shadowOpacity: 0.06,
    shadowRadius: 20,
    elevation: 3,
  },
  sheet: {
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: -4 },
    shadowOpacity: 0.12,
    shadowRadius: 24,
    elevation: 12,
  },
  fab: {
    shadowColor: '#0f5238',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.24,
    shadowRadius: 12,
    elevation: 6,
  },
} as const;

export type ColorToken = keyof typeof colors;
