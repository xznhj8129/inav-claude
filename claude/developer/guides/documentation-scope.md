# Where Documentation Belongs: inav/inav-configurator vs. inav-claude

Quick reference for deciding which repo a piece of developer documentation
belongs in. Written after several rounds of extracting docs from
`claude/developer/docs/` into `inav/docs/development/` and
`inav-configurator/docs/development/`.

- **Default to `inav/` or `inav-configurator/`** if the content is a durable,
  verifiable fact about how the codebase or its build/branch/release process
  works — true for any contributor, not just an AI agent.
- **Keep it in `inav-claude`** if it names Claude, an agent, or a slash
  command, OR if its *methodology* is something only an AI agent would do
  even without naming one (e.g. bulk-grepping raw `.kicad_sch`/`.SchDoc`
  text — a human would open a PDF/schematic viewer instead).
- **Keep it in `inav-claude`** if it's session narrative — what happened,
  who decided what, why a mistake occurred — rather than a standing fact
  about the code. Test: would this sentence still be true and useful a year
  from now, with no memory of this conversation?
- **Never move content you haven't personally verified** against current
  source. Prefer citing function/setting names over line numbers or fixed
  values (e.g. `SETTING_*_DEFAULT` macros, not a literal default) so the doc
  doesn't rot as the code changes.
- **Vendor Content Policy:** never copy manufacturer datasheet/schematic
  content into `inav/` or `inav-configurator/` docs, even paraphrased.
  Referencing a vendor doc by name/section (e.g. "see section 4 of the
  H743 reference manual") is fine — it's the content itself that can't be
  copied in.
- When genuinely unsure, ask: "would this doc make sense to a human
  contributor with no `inav-claude` context at all?" If no, it stays here.
