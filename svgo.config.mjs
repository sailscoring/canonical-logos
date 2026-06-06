// SVGO config used by scripts/02_normalise.py for vector logo assets.
//
// Conservative: strip metadata/title/desc/editor cruft and collapse groups,
// but PRESERVE IDs (logos commonly use <use> / gradient / clipPath references
// that break if IDs are renamed or dropped) and keep enough path precision
// that fine logo geometry survives.
//
// This is format/size normalisation only — it must never alter the colours or
// composition of a mark (see the licensing posture in README.md). Do not add
// plugins that recolour, convert shapes destructively, or merge paths in ways
// that change appearance.

export default {
  multipass: true,
  floatPrecision: 3,
  plugins: [
    {
      name: "preset-default",
      params: {
        overrides: {
          cleanupIds: false,
          // Keep viewBox; the results-header slot scales by height.
          removeViewBox: false,
        },
      },
    },
    "removeTitle",
    "removeDesc",
    "removeMetadata",
    "removeEditorsNSData",
  ],
};
