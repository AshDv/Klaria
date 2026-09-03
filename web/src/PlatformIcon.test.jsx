import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlatformIcon } from "./PlatformIcon";

describe("PlatformIcon", () => {
  it.each([
    ["google", "Google Calendar"],
    ["google_meet", "Google Meet"],
    ["microsoft", "Microsoft Teams"],
    ["teams", "Microsoft Teams"],
  ])("rend %s avec un nom accessible", (platform, label) => {
    render(<PlatformIcon platform={platform} />);
    expect(screen.getByRole("img", { name: label })).toBeInTheDocument();
  });

  it("masque une icône décorative", () => {
    const { container } = render(<PlatformIcon platform="google" decorative />);
    expect(container.querySelector("[aria-hidden='true']")).toBeInTheDocument();
  });

  it("utilise un fallback pour une plateforme inconnue", () => {
    const { container } = render(<PlatformIcon platform="unknown" />);
    expect(container.querySelector(".platform-fallback")).toHaveTextContent("●");
  });
});
