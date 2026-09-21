import { useEffect, useState } from "react";

import { NAVIGATION_SECTIONS } from "../domain/data";
import type { SectionId } from "../domain/model";

const VALID_SECTIONS = new Set<SectionId>(NAVIGATION_SECTIONS.map((section) => section.id));

function sectionFromHash(): SectionId {
  const candidate = window.location.hash.replace(/^#\/?/, "") as SectionId;
  return VALID_SECTIONS.has(candidate) ? candidate : "overview";
}

export function useHashRoute() {
  const [section, setSection] = useState<SectionId>(() => sectionFromHash());

  useEffect(() => {
    const handleHashChange = () => {
      setSection(sectionFromHash());
      window.scrollTo({ top: 0, behavior: "smooth" });
    };
    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  const navigate = (nextSection: SectionId) => {
    if (nextSection === section) {
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    window.location.hash = nextSection;
  };

  return { section, navigate };
}
