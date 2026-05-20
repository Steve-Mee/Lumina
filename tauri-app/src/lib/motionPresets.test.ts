import { describe, expect, it } from "vitest";

import {
  menuPopWith,
  panelCrossfadeWith,
  springSnappy,
  staggerItemWith,
} from "@/lib/motionPresets";

describe("motionPresets factories", () => {
  const customTransition = { type: "spring" as const, stiffness: 100, damping: 20 };

  it("menuPopWith embeds the passed transition", () => {
    const variants = menuPopWith(customTransition);
    expect(variants.visible).toMatchObject({ transition: customTransition });
    expect(variants.exit).toMatchObject({ transition: customTransition });
  });

  it("panelCrossfadeWith embeds the passed transition", () => {
    const variants = panelCrossfadeWith(customTransition);
    expect(variants.visible).toMatchObject({ transition: customTransition });
    expect(variants.exit).toMatchObject({ transition: customTransition });
  });

  it("staggerItemWith embeds the passed transition", () => {
    const variants = staggerItemWith(customTransition);
    expect(variants.visible).toMatchObject({ transition: customTransition });
  });

  it("default menuPop uses springSnappy", () => {
    const variants = menuPopWith(springSnappy);
    expect(variants.visible).toMatchObject({ transition: springSnappy });
  });
});
