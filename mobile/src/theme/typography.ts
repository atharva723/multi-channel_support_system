/**
 * Typography scale (Stitch spec).
 *
 * Display face: Plus Jakarta Sans (rounded, friendly, bold headings).
 * Body face:    Hanken Grotesk (legible workhorse for tickets/drafts).
 *
 * Font family keys map to the names registered via @expo-google-fonts in the
 * root layout's font loader.
 */

export const fonts = {
  jakarta: 'PlusJakartaSans_400Regular',
  jakartaMedium: 'PlusJakartaSans_500Medium',
  jakartaSemibold: 'PlusJakartaSans_600SemiBold',
  jakartaBold: 'PlusJakartaSans_700Bold',
  jakartaExtrabold: 'PlusJakartaSans_800ExtraBold',
  hanken: 'HankenGrotesk_400Regular',
  hankenMedium: 'HankenGrotesk_500Medium',
  hankenSemibold: 'HankenGrotesk_600SemiBold',
  hankenBold: 'HankenGrotesk_700Bold',
} as const;

export const type = {
  displayXl: {
    fontFamily: fonts.jakartaExtrabold,
    fontSize: 44,
    lineHeight: 48,
    letterSpacing: -1.4,
  },
  headlineLg: {
    fontFamily: fonts.jakartaBold,
    fontSize: 32,
    lineHeight: 38,
    letterSpacing: -0.6,
  },
  headlineMd: {
    fontFamily: fonts.jakartaBold,
    fontSize: 26,
    lineHeight: 32,
    letterSpacing: -0.4,
  },
  titleMd: {
    fontFamily: fonts.jakartaSemibold,
    fontSize: 20,
    lineHeight: 26,
    letterSpacing: -0.2,
  },
  titleSm: {
    fontFamily: fonts.jakartaSemibold,
    fontSize: 17,
    lineHeight: 22,
  },
  bodyLg: {
    fontFamily: fonts.hanken,
    fontSize: 17,
    lineHeight: 26,
  },
  bodyMd: {
    fontFamily: fonts.hanken,
    fontSize: 15,
    lineHeight: 22,
  },
  labelMd: {
    fontFamily: fonts.hankenSemibold,
    fontSize: 13,
    lineHeight: 18,
  },
  labelSm: {
    fontFamily: fonts.hankenMedium,
    fontSize: 11,
    lineHeight: 15,
    letterSpacing: 0.4,
  },
} as const;

export type TypeToken = keyof typeof type;
