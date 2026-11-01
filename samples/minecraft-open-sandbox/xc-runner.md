# XC runner — same product prompt, no extra product requirements

Use this only for the XC run. The product prompt is exactly `prompt.md`; do not add features,
quality requirements, non-goals or scope decisions to it.

1. Work in the isolated consumer project. Start from the same `seed/` as the one-shot run.
2. Use the installed XC managed workflow (`xc-work`) through its public interface. Keep the normal
   lifecycle and artifacts. Do not read the one-shot workspace, the public sample, prior results or
   the evaluation standard/profile before implementation.
3. The product request is:
   > Build a playable, offline 2D sandbox game inspired by Minecraft.
   > It must run by opening `index.html`, with no build step, external libraries, CDNs, or network
   > access. Make it feel like a small Minecraft, save progress, and document the controls.
4. Do not add extra product requirements. In particular, do not add or forbid crafting, survival,
   mobs, redstone or any other Minecraft system by fiat. Those are decisions the implementation and
   its analysis must make from the request and the reference; record them.
5. Do not use the old compact sample's profile or its non-goal list. That profile belongs to a
   different sample.
6. Verify the result (tests/browser) and record evidence. Do not create a project Git commit; the
   enclosing repository owns the sample commit.
