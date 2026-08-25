const logos = {
  google: "https://fonts.gstatic.com/s/i/productlogos/calendar_2020q4/v13/192px.svg",
  google_meet: "https://fonts.gstatic.com/s/i/productlogos/meet_2020q4/v6/192px.svg",
  microsoft: "https://teams.public.onecdn.static.microsoft/evergreen-assets/icons/microsoft_teams_logo_refresh_v2025.ico",
  teams: "https://teams.public.onecdn.static.microsoft/evergreen-assets/icons/microsoft_teams_logo_refresh_v2025.ico",
};

const labels = {
  google: "Google Calendar",
  google_meet: "Google Meet",
  microsoft: "Microsoft Teams",
  teams: "Microsoft Teams",
};

export function PlatformIcon({ platform, className = "", decorative = false }) {
  const src = logos[platform];
  if (!src) return <span className={`platform-fallback ${className}`} aria-hidden="true">●</span>;
  return <img
    className={`platform-logo ${className}`}
    src={src}
    alt={decorative ? "" : labels[platform]}
    aria-hidden={decorative || undefined}
  />;
}
